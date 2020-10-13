import pexpect
import subprocess
import signal
import re
import time
import os
import sys
from time import sleep

from tkinter import Tk, StringVar,Frame,Label,Button,Scrollbar,Listbox,Entry,Text
from tkinter import Y,END,TOP,BOTH,LEFT,RIGHT,VERTICAL,SINGLE,NONE,NORMAL,DISABLED
from datetime import datetime, timezone


class VLCDriver(object):
    start_time=0  # for logging


    def init(self):
        VLCDriver.start_time=time.time() # for log
        self.log_file=open('/home/pi/dbusvlc/log.txt','a')
        self.log('--init--')
        
        
    # used first time and for every other instance
    def __init__(self,root):
        self.work_dir=sys.path[0]
        self.log_file=open(self.work_dir+'/log.txt','a')
        self.log('\n\n--init track instance--')
        self.root=root  #use tkinter for timers
        self.vlcp=None
        self.loop_timer=None
        self.terminate_signal=False

    # API function
    # track,display,x,y,width,height,volume,(pause at start = before,after,no),loaded callback
    def load(self, track,display, video_x,video_y,width,height,volume,pause_at_start,loaded_callback):
        self.track=track
        self.volume=volume
        self.loaded_callback=loaded_callback
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
        mmal_display= ['--mmal-display='+display]
        mmal_layer= ['--mmal-layer=1']
        volume_opt= ['--volume='+str(self.volume)]
        title_opt = ['--no-video-title-show']

        vlc_cmd=vlc_template + vout_cmd + mmal_val + mmal_display + mmal_layer + volume_opt + pause_opt\
         + title_opt + window_opt + trans_opt
        cmd=' '.join(vlc_cmd)
        self.log ('New instance created to play a track\n',cmd,'\n')
        self.vlcp = pexpect.spawn('/bin/bash', ['-c', cmd])
        # uncomment to monitor output to and input from cvlc (read pexpect manual)
        #fout= file('/home/pi/dbusvlc/vlclog.txt','w')  #uncomment and change sys.stdout to fout to log to a file
        #self.vlcp.logfile_send = sys.stdout  # send just commands to stdout
        #self.vlcp.logfile=fout  # send all communications to log file
        self.log ('started at volume',volume_opt[0])
        
        # start a track
        self.vlcp.send('add '+track+'\n')
        self.log('add track',track)
        self.set_volume(self.volume)
        #delay to let vlc print its version  etc.
        self.root.after(100,self.wait_for_crap) #500

    # having waited for the crap to be produced send get_length and then detect its echo
    # so we know all the crap has gone
    def wait_for_crap(self):
        self.vlcp.send('get_length\n')
        self.vlcp.expect_exact(b'get_length\r\n')
        #stop echoing the commands from now on.
        #self.log ('found get_length',self.vlcp.before,self.vlcp.after)
        self.vlcp.setecho(False)

        #now get ready to show the track
        self.duration=self.get_duration_ffprobe(self.track)*1000
        self.log ('track duration',self.duration)
        self.track_start_time=time.time()
        self.past_pause_length=0
        self.length_to_current_pause=0
        self.loop_timer=self.root.after(1,self.load_status_loop)
        return


    def load_status_loop(self):
        # wait for load to complete
        # track has been loaded in a paused state
        if self.pause_at_start=='before':
            self.log ('pause before start ')
            self.loaded_callback()
            return
        
        #track is not paused, wait for it to load    
        success,position = self.get_track_start()
        if success != 'normal':
            self.loop_timer=self.root.after(1,self.load_status_loop)
            return
        self.log (position,self.load_pause_position)
        if position >= self.load_pause_position: #milliseconds
            if self.pause_at_start == 'after':
                self.pause_on()
                self.log ('pause after start at ',position)
                self.loaded_callback()
                return
            else:
                self.log ('no pause at start')
                self.loaded_callback()
                return
        else:
            self.loop_timer=self.root.after(1,self.load_status_loop)



    # API function
    def show(self,pause_at_end,previous,end_callback):
        self.previous_player=previous
        self.pause_at_end=pause_at_end
        self.end_callback=end_callback
        self.log ('set volume at show',self.volume)
        self.set_volume(self.volume)
        # let the video play but wait until it shows on screen before removing previous track
        self.pause_off()
        # wait for track to start showing
        self.root.after(1,self.wait_for_start)
        
    #wait until the video starts indicated by vlc's get_time not returning 0 or more
    def wait_for_start(self):
        success,position= self.get_track_start()
        self.log ('wait start',position)
        if position <0:
            self.root.after(1,self.wait_for_start)
        else:
            # first non-zero Position
            self.log('detected first frame',position)

            self.track_start_time=time.time()
            self.past_pause_length=0
            self.track_length=0
            self.root.after(1,self.show_status_loop)
            self.root.after(200,self.finish_previous)       # magic number to reduce the gap without the two tracks overlaying    
 
    # stop the previous track
    def finish_previous(self):
        if self.previous_player!=None:
            self.log('Finish Previous')
            self.previous_player.stop()
            #self.previous_player=None 

            
    def show_status_loop(self):
        if self.terminate_signal is True:
            self.terminate_signal=False
            self.end_callback('quit')
            return
            
        success,position= self.get_ms_time()
        if success not in ('normal','empty'):
            self.log ('Fail Get Show Position')
            self.end_callback('quit')
            return
        else:
            #self.log ('position',str(position))
            if self.pause_at_end == 'yes':
                #must pause before the end of traack else track repeats
                if position >= self.duration-1000:   #milliseconds. magic number so track always pauses before it ends
                    self.pause_on()
                    self.log ('paused at end ',position)
                    self.end_callback('pause_at_end')
                else:
                    self.loop_timer=self.root.after(20,self.show_status_loop)
            else:
                if self.pause_at_end == 'no':
                    if success == 'empty':
                        self.stop()
                        self.log ('ended with no pause at ',position)
                        self.end_callback('nice_day')
                    else:
                        self.loop_timer=self.root.after(20,self.show_status_loop)
                else:
                    self.log( 'illegal pause at end')


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


    def get_track_start(self):
    # detect when track starts displaying by detecting get_time returning 0
    # not nice because get-time blocks for 50mS.

        #self.log('before send',time.time()) 
        self.vlcp.send('get_time\n')
        # send takes 50 mS!!!!!
        #self.log('after send',time.time()) 
        time_str=self.vlcp.readline()
        #self.log ('after readline',time.time())      
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

    """
    #### old stuff
    
    # get the time into the track from vlc and interpolate between seconds
    # not used because get-time blocks for 50mS.
    def get_ms_time(self):
        if self.paused:
            return 'normal',self.time
        #print ('before',time.time())
        self.vlcp.send('get_time\n')
        time_str=self.vlcp.readline()
        # this takes 50 mS!!!!!
        #print ('after',time.time())      
        found_digit,val=self.strtoint(time_str)
        if found_digit is True:
            if val>self.time_sec:
                self.time_sec=val
                self.time_delta=0
                #print (self.time_sec)
            else:
                self.time_delta += 100   # need to use real time
            time_ms=self.time_sec*1000 + self.time_delta
            #print ('time OK',self.time_sec,self.time_delta,time_ms,time.time())
            return 'normal',time_ms
        else:
            #empty reply so at end of track, make one inc
            self.time_delta += 100   # need to use real time
            time_ms=self.time_sec*1000 + self.time_delta
            #print ('get_time no digit',time_str,found_digit,val) 
            return 'empty',time_ms 


    def get_position(self):
        #print('poll')
        
        status,self.time= self.get_ms_time()
        if status != 'normal':
            print( 'get_time failed')
            return 
         
        if self.pause_at_start=='before'and self.time>=self.load_pause_position:
            self.pause_on()
            self.pause_at_start='done'
            
        if self.pause_at_start=='after'and self.time >= self.load_pause_position:
            self.pause_on()
            self.pause_at_start='done'
            
        if self.terminate_signal is True:
            self.terminate_signal=False
            return
        else:
            self.poll_timer=self.root.after(50,self.get_position)
            
    def bin(self,uni):
        return uni.encode(encoding='UTF-8')

    def debin(self,uni):
        return uni.decode(encoding='UTF-8')
    """


            


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
            self.log('input event not known',name)

    # used outside showing
    def pause_on(self,event=None):
        if self.paused is False:
            self.log ('system pause on')
            self.vlcp.send('pause\n')
            self.paused=True
        
    def pause_off(self,event=None):
        if self.paused is True:
            self.log ('system pause off ')
            self.vlcp.send('pause\n')
            self.paused=False
            
            
    # used during showing to adjust time into track
    def pause_show_off(self):
        if self.paused is True:
            self.log ('show pause off ')
            self.past_pause_length+=(time.time()-self.current_pause_start_time)*1000
            self.vlcp.send('pause\n')
            self.paused=False
            
    def pause_show_on(self):
        if self.paused is False:
            self.log ('show pause on')
            self.current_pause_start_time=time.time()
            self.current_pause_length=0
            self.length_to_current_pause=self.track_length
            self.vlcp.send('pause\n')
            self.paused=True
            
    def set_volume(self,volume):
        self.vlcp.send('volume '+ str(volume)+'\n')
        return
        

    def stop(self):
        self.vlcp.send('stop\n')

    def terminate(self):
        self.terminate_signal=True
        if self.vlcp !=None:
            self.vlcp.sendintr()
        if self.loop_timer!=None:
            self.root.after_cancel(self.loop_timer)

    def log(self,*args):
        al=[]
        for arg in args:
            string_arg=str(arg)
            al.append(string_arg)
        text=' '.join(al)
        #.strftime("%A %d %B %Y %I:%M:%S%p")
        time_str="{:.6f}".format(time.time()-VLCDriver.start_time)
        print(time_str,text)
        self.log_file.write(time_str+ '     ' + text + '\n')
        self.log_file.flush()





# -------------------------------
# Test harness
# -------------------------------


class PiPresents(object):


    def __init__(self):
        # root is the Tkinter root widget
        self.root = Tk()
        self.root.title("VLC in Pi Presents Investigation")

        # self.root.configure(background='grey')

        self.root.resizable(False,False)
        self.root.geometry("%dx%d%+d%+d"  % (200,200,400,400))

        # define response to main window closing
        self.root.protocol ("WM_DELETE_WINDOW", self.app_exit)

        self.root.bind("<Key>", lambda event : self.normal_key(event))
        self.root.bind('<Escape>',self.app_exit)
        
        #Init the VLC Driver
        # init starts a dummy instance of VLC. Seems to be required to make DBUS work
        self.vlc=VLCDriver(self.root)
        self.vlc.init()
        
        # list of instances of VLC other than the initial dummy
        self.vlc_list=[]
        
        # and start Tkinter mainloop
        self.root.mainloop()


    def normal_key(self,event):
        key=event.char
        if key == "1":
            self.play1()
        elif key == "2":
            self.play2()
        elif key == "3":
            self.play3()
        else:
            #offer the key to all the tracks
            for track in self.vlc_list:
                track.input_event(key)
            

    def app_exit(self,event=None):
        # terminate all the track vlc's
        for vlcs in self.vlc_list:
            vlcs.terminate()
        self.root.destroy()
        exit()

    # track 1 only
    def play1(self):
        self.vlc.log ('play1')
        self.od1=VLCDriver(self.root)
        self.vlc_list.append(self.od1)
        # track,x,y,width,height,(volume 0>1024), (pause at start = before,after,no),loaded callback
        self.od1.load('5sec.mp4','HDMI-1',100,400,100,100,256,'no',self.loaded1_callback)

    def loaded1_callback(self):
        self.vlc.log ('loaded 1')
        # (pause at end = yes,no), previous player, end callback
        self.od1.show('no',None,self.end1_callback)
        
    def end1_callback(self,status):
        self.vlc.log ('ended 1',status)
        self.vlc_list.remove(self.od1)


    # track 2 only
    def play2(self):
        self.vlc.log ('play 2')
        self.od2=VLCDriver(self.root)
        self.vlc_list.append(self.od2)
        # track,x,y,width,height,(pause at start = before,after,no),loaded callback
        self.od2.load('5sec.mp4','HDMI-2',100,100,100,100,256,'no',self.loaded2_callback)

    def loaded2_callback(self):
        self.vlc.log ('loaded 2')
        # (pause at end = yes,no), end callback
        self.od2.show('no',None,self.end2_callback)
        
    def end2_callback(self,status):
        self.vlc.log ('ended 2',status)
        self.vlc_list.remove(self.od2)


    def play3(self):
        # play first track normally
        self.vlc.log ('load 3')
        self.od3=VLCDriver(self.root)
        self.vlc_list.append(self.od3)
        # track,x,y,width,height,(pause at start = before,after,no),loaded callback
        self.od3.load('5sec.mp4','HDMI-1',100,100,200,200,256,'no',self.loaded3_callback)

    def loaded3_callback(self):
        self.vlc.log ('loaded 3')
        # pause at end until next track is loaded.
        self.vlc.log ('start show 3')
        self.od3.show('yes',None,self.end3_callback)
        
    def end3_callback(self,status):
        self.vlc.log ('end show 3',status)
        if status == 'pause_at_end':
            self.vlc.log ('pause at end so load 4')
            self.od4=VLCDriver(self.root)
            self.vlc_list.append(self.od4)
            self.od4.load('xthresh.mp4','HDMI-1',200,200,300,300,64,'before',self.loaded4_callback)
            # bodge - this should be done in vlcdriver whch should then return with nice_day
            self.od3.stop()
            self.vlc_list.remove(self.od3)            
        else:
            #quit or nice_day, just return
            # get out of the callback
            self.vlc.log ('ending 3  other than pause at end',status)
            self.vlc_list.remove(self.od3)
            self.root.after(1,self.finished)

            
    def loaded4_callback(self):
        self.vlc.log ('loaded 4')
        self.vlc.log ('start showing 4')        
        self.od4.show('no',self.od3,self.end4_callback)

        
    def end4_callback(self,status):
        self.vlc.log ('end show 4',status)
        self.vlc_list.remove(self.od4)
        self.root.after(1,self.finished)
        
    def finished(self):
        self.vlc.log ('finished')
        return
    
    
if __name__ == '__main__':    
    pp=PiPresents()
 

