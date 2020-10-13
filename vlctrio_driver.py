from vlctrio_logger import Logger
import pexpect
import subprocess
import trio
import time
class VLCDriver():
    
    def __init__(self,nursery):
        # used for every instance
        self.nursery=nursery
        self.logger=Logger()
        self.logger.log('--init track instance--')
        self.vlcp=None

    # track,display,x,y,width,height,volume,(pause at start = before,after,no)
    async def load(self, track,display_name, video_x,video_y,width,height,volume,pause_at_start):
        print('load')
        self.track=track
        self.volume=volume
        self.pause_at_start=pause_at_start
        #calculate position and option for pause at start
        if self.pause_at_start=='before':
            pause_opt=['--start-paused']
            self.load_pause_position=0   #not used
            self.paused=True
        elif self.pause_at_start=='after':
            self.load_pause_position = 0
            pause_opt=['--no-start-paused']
            self.paused=False
        else:
            # no pause at start
            pause_opt=['--no-start-paused']
            self.paused=False
            # position always greater than this
            self.load_pause_position=-2

        #prepare command for VLC
        vlc_template = ['DISPLAY= ','cvlc', '-I', 'rc','--play-and-stop','--quiet']
        window=str(width)+'x'+str(height)+'+'+str(video_x)+'+'+str(video_y)
        window_opt= ['--mmal-vout-window='+window]
        trans_opt = ['--mmal-vout-transparent']
        vout_cmd = ['-V']
        mmal_val = ['mmal_vout']
        mmal_display= ['--mmal-display='+display_name]
        mmal_layer= ['--mmal-layer=1']
        volume_opt= ['--volume='+str(self.volume)]
        title_opt = ['--no-video-title-show']

        vlc_cmd=vlc_template + vout_cmd + mmal_val + mmal_display + mmal_layer + volume_opt + pause_opt\
         + title_opt + window_opt + trans_opt
        cmd=' '.join(vlc_cmd)
        self.logger.log ('New instance created to play a track\n',cmd,'\n')
        self.vlcp = pexpect.spawn('/bin/bash', ['-c', cmd])
        # uncomment to monitor output to and input from cvlc (read pexpect manual)
        #fout= file('/home/pi/dbusvlc/vlclog.txt','w')  #uncomment and change sys.stdout to fout to log to a file
        #self.vlcp.logfile_send = sys.stdout  # send just commands to stdout
        #self.vlcp.logfile=fout  # send all communications to log file
        self.logger.log ('started at volume',volume_opt[0])
        
        # start a track
        self.vlcp.send('add '+track+'\n')
        self.logger.log('add track',track)
        self.set_volume(self.volume)
        #delay to let vlc print its version  etc.
        await trio.sleep(0.1)
        self.wait_for_crap()
        await self.load_status_loop()


    # having waited for the crap to be produced send get_length and then detect its echo
    # so we know all the crap has gone
    def wait_for_crap(self):
        self.vlcp.send('get_length\n')
        self.vlcp.expect_exact(b'get_length\r\n')
        #stop echoing the commands from now on.
        #self.logger.log ('found get_length',self.vlcp.before,self.vlcp.after)
        self.vlcp.setecho(False)

        #now get ready to show the track
        self.duration=self.get_duration_ffprobe(self.track)*1000
        self.logger.log ('track duration',self.duration)
        self.track_start_time=time.time()
        self.past_pause_length=0
        self.length_to_current_pause=0
        return


    async def load_status_loop(self):
        # wait for load to complete
        # track has been loaded in a paused state
        if self.pause_at_start=='before':
            self.logger.log ('pause before start ')
            return
        
        #track is not paused, wait for it to load
        while True:    
            success,position = self.get_track_start()
            if success != 'normal':
                self.logger.log('wait for start')
                await trio.sleep(1)
                continue

            self.logger.log ('found start',position,self.load_pause_position)
            if position >= self.load_pause_position: #milliseconds
                if self.pause_at_start == 'after':
                    self.pause_on()
                    self.logger.log ('pause after start at ',position)
                    return
                else:
                    self.logger.log ('no pause at start')
                    return
            else:
                await trio.sleep(1)


    def get_track_start(self):
    # detect when track starts displaying by detecting get_time returning 0
    # not nice because get-time blocks for 50mS.

        #self.logger.log('before send',time.time()) 
        self.vlcp.send('get_time\n')
        # send takes 50 mS!!!!!
        #self.logger.log('after send',time.time()) 
        time_str=self.vlcp.readline()
        #self.logger.log ('after readline',time.time())      
        found_digit,val=self.strtoint(time_str)
        if found_digit is True:
            return 'normal',val
        else:
            return 'empty',-1


    # use ffprobe to get exact duration of the track
    def get_duration_ffprobe(self,filename):
        result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                                 "format=duration", "-of",
                                 "default=noprint_wrappers=1:nokey=1", filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        return float(result.stdout)          


    # converts byte string from vlc to integer
    def strtoint(self,bts):
        result=0
        found_digit=False
        if len(bts)==0:
            return found_digit,-1
        for bt in bts:
            if bt>=48 and bt<58:
                val=bt-48
                result=10*result+val
                found_digit=True
        return found_digit,result


    #API FUNCTION
    async def show(self,pause_at_end,previous):
        print('show')
        self.previous_player=previous
        self.pause_at_end=pause_at_end
        self.logger.log ('set volume at show',self.volume)
        self.set_volume(self.volume)
        # let the video play but wait until it shows on screen before removing previous track
        self.pause_off()
        # wait for track to start showing
        await self.wait_for_start()
        #self.nursery.start_soon(self.finish_previous) #start a task to do this as needs parallel execution
        status = await self.show_status_loop()
        return status
        
    #wait until the video starts indicated by vlc's get_time not returning 0 or more
    async def wait_for_start(self):
        while True:
            success,position= self.get_track_start()
            self.logger.log ('wait start',position)
            if position <0:
                await trio.sleep(0.01)
                continue
            # first non-zero Position
            self.logger.log('detected first frame',position)
            self.track_start_time=time.time()
            self.past_pause_length=0
            self.track_length=0
            self.stop_signal=False
            return

                 
    # stop the previous track
    async def finish(self):
        await trio.sleep(0.2)  # magic number to reduce the gap without the two tracks overlaying    
        self.logger.log('finish previous')
        #if self.previous_player!=None:
        self.logger.log('Finished Previous')
        self.stop()
            #self.previous_player=None 

            
    async def show_status_loop(self):
        while True:

            if self.stop_signal is True:
                self.stop_signal=False
                return 'quit'
                
            success,position= self.get_ms_time()
            if success not in ('normal','empty'):
                self.logger.log ('Fail Get Show Position')
                return 'quit'
            else:
                #self.logger.log ('position',str(position))
                if self.pause_at_end == 'yes':
                    #must pause before the end of track else track repeats
                    if position >= self.duration-1400:   #milliseconds. magic number so track always pauses before it ends
                        self.pause_on()
                        self.logger.log ('paused at end ',position)
                        return 'pause_at_end'
                    else:
                        await trio.sleep(0.02)
                        continue
                else:
                    if self.pause_at_end == 'no':
                        if success == 'empty':
                            self.stop()
                            self.logger.log ('ended with no pause at ',position)
                            return 'nice_day'
                        else:
                            await trio.sleep(0.02)
                            continue
                    else:
                        self.logger.log( 'illegal pause at end')
                        return 'quit'

    def get_ms_time(self):
        # since vlc's get_time is accurate to only 1 sec and blocks need to calc time into track 
        # by using time.time()
        #time in secs, length in mS.
        if self.paused is True:
            # time into this pause
            self.current_pause_length=(time.time()-self.current_pause_start_time)*1000 
            #print ('PAUSED',self.track_length,'=',self.length_to_current_pause,self.current_pause_length)
        else:
            self.track_length=(time.time()- self.track_start_time)*1000 -self.past_pause_length
            #print ('RUNNING',self.track_length,'=',(time.time()- self.track_start_time)*1000,self.past_pause_length)
        if self.track_length >=self.duration:
            return 'empty',-1
        else:
            return ('normal',self.track_length)


# ***********************
# Commands
# ***********************

    def input_event(self,name):
        if name == 'u':
            self.pause_show_off()
        elif name=='p':
            self.pause_show_on()
        elif name== 'q':
            self.stop()
        else:
            self.logger.log('input event not known',name)

    # used outside showing
    def pause_on(self,event=None):
        if self.paused is False:
            #self.logger.log('before')
            self.vlcp.send('pause\n')
            #self.logger.log('after')
            self.logger.log ('system pause on')
            self.paused=True
        
    def pause_off(self,event=None):
        if self.paused is True:
            self.logger.log ('system pause off ')
            self.vlcp.send('pause\n')
            self.paused=False
            
            
    # used during showing to adjust time into track
    def pause_show_off(self):
        if self.paused is True:
            self.logger.log ('show pause off ')
            self.past_pause_length+=(time.time()-self.current_pause_start_time)*1000
            self.vlcp.send('pause\n')
            self.paused=False
            
    def pause_show_on(self):
        if self.paused is False:
            self.logger.log ('show pause on')
            self.current_pause_start_time=time.time()
            self.current_pause_length=0
            self.length_to_current_pause=self.track_length
            self.vlcp.send('pause\n')
            self.paused=True
            
    def set_volume(self,volume):
        self.vlcp.send('volume '+ str(volume)+'\n')
        return
        

    def stop(self):
        self.logger.log('stop')
        self.stop_signal = True
        self.vlcp.send('stop\n')
        self.vlcp.send('quit\n')



