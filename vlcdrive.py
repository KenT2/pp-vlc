"""
veneer for vlc which allows vlc to be controlled by libvlc when using the PI's --vout mm-vout display driver
while at the same time inhibiting VLC's extraneous x-window based video window.

python bindings for libvlc are here http://www.olivieraubert.net/vlc/python-ctypes/doc/

I intend to use a production version of this because I wanted accurate reporting of track positon which the -rc interface module does not allow.

This is incomplete and untested software with little error checking.

INSTALL
libvlc python bindings are required sudo pip3 install python-vlc
If track is not specified then a track from the current directory is used (see self.track_path)
Must be run with DISPLAY= python3 vlcdrive.py to hide VLC's black background
log output goes the driver_log.txt (see Logger Class)

USE

The driver has a command line interface, either type commands into terminal or use vlcplay.py
which accesses the interface through pexpect.
After the start message line there is no prompt, type the command followed by return.

commands
ipots - supply a set of options for a VLC instance iopts <option> <option> .......
popts - pause options   popts <pause-at-start>  <pause-at-end> 
        pause-at-start before/after/no - pause before or after first frame, no is not tested
        pause-at-end  yes/no   - pause before last frame or run on to track is finished.
track - path of track to play track <full track path>

l - load a track and then run to start as in popts. Load is non-blocking and returns immeadiately. To determine load is complete poll using the t command to obtain the state
    idle - track not loading or showing
    load-loading - load in progress
    load-ok - loading complete and ok
    load-fail

s - show a track that has been loaded. Show is non-blocking and returns immeadiately. To determine showing is complete poll using the t command to obtain the state
    idle - track not loading or showing
    show-showing - showing in progress
    show-pauseatend - paused before last frame
    show-niceday - track has ended, q command required to shut process down
    show-fail
    
q - stops showing a loading and closes vlc
    
t - get the current state of loading/showing. Returns a single line wit hone of the above values

vol - set the volume between 0 and 100. Use only when showing  vol <volume>
      Volume is set to 0 in load so need to send aafter s command to hear anything
 
"""

import time
import threading
import sys
import vlc #sudo pip3 install python-vlc

class VideoPlayer(object):
    
    # used first time and for every other instance
    def __init__(self):
        self.work_dir=sys.path[0]
        self.logger=Logger()
        self.logger.log('')
        self.logger.log('init VLC instance')
        self.quit_load_signal=False
        self.quit_show_signal=False
        self.instance_options=' --mmal-layer=1 --mmal-vout-window 400x300+100+100 --mmal-vout-transparent --aout=pulse --mmal-display=HDMI-1 '         # obtained from iopts command, just a default set
        self.player_options=''             #options for mediaplayer, none required
        self.instance_mandatory=' --quiet --no-xlib --vout mmal_vout '   #mandatory set of options
        self.track_path= self.work_dir+'/xthresh.mp4'   #track to play
        self.pause_at_start='before'       #default, normally obtained from pauseopts command
        self.pause_at_end='no'           #default, normally obtained from pauseopts command
        self.aspect_ratio = ''          #default, normally obtained from propts command
        self.crop =''                    #default, normally obtained from propts command
        self.show_status_thread=None
        self.load_status_thread=None
        self.volume=100
        self.state='idle'

# --no-xlib 

    def load(self):
        
        self.state='load-loading'

        # create a vlc instance
        options=self.instance_mandatory+self.instance_options
        self.logger.log('Instance Options: ',options)       
        self.vlc_instance = vlc.Instance(options)
        
        #print ('enumerate devices',self.vlc_instance.audio_output_enumerate_devices())
        #print ('device list',self.vlc_instance.audio_output_device_list_get('pulse'))

        # get the media and obtain its length
        self.media = self.vlc_instance.media_new(self.track_path)
        self.media.parse()
        self.length=self.media.get_duration()
        self.logger.log ('track length',self.length)
        
        self.player = vlc.MediaPlayer(self.vlc_instance,'',self.player_options)
        self.set_volume(0)
        #print ('player device _enum',self.player.audio_output_device_enum())
        self.player.set_media(self.media)
        self.logger.log(self.crop,self.aspect_ratio)
        self.player.video_set_crop_geometry(self.crop)
        self.player.video_set_aspect_ratio(self.aspect_ratio)
        self.player.play()

        #calculate position for pause at start
        if self.pause_at_start=='before':
            # before first frame, pause when first 0 get_time() report is received
            self.load_pause_position=-1
        elif self.pause_at_start=='after':
            # after first frame, when get_time() >0 allowing for sampling rate.
            self.load_pause_position = 200
        else:
            # no pause  - arbitrary large number - probably not used in PP.
            self.load_pause_position=1000000000
        

        #monitor the loading of the track using a thread so can receive commands during the load
        self.load_status_thread= threading.Thread(target=self.load_status_loop)
        self.load_status_thread.start()
        return



    def load_status_loop(self):
        # wait until the load is complete
        #need a timeout as sometimes a load will fail 
        timeout= 1000   #10 seconds
        # Number of zeros after the first zero to get pause before to work best
        zero_count= 2
        while True:
            if self.quit_load_signal is True:
                self.quit_load_signal=False
                self.state= 'idle'
                return
            position=self.player.get_time()
            #print (position,zero_count)
            if position > self.load_pause_position and zero_count<0: #milliseconds
                if self.pause_at_start != 'no':
                    self.pause_on()
                    self.logger.log ('track paused after load',position)
                    self.state='load-ok'
                    #print (self.state)
                    return
                else:
                    self.logger.log ('load complete no pause')
                    self.state='load-ok'
                    #print (self.state)
                    return
            timeout-=1
            if timeout <=0:
                    self.state='load-fail'
                    #print (self.state)
                    return
            else:
                # first frame does not appear until after a number of 0 position frames
                if position ==0:
                    zero_count-=1
                time.sleep(0.01)


    def show(self):
        self.state='show-showing'
        self.pause_off()
        self.logger.log ('pause off, start showing')
        self.show_status_thread=threading.Thread(target=self.show_status_loop)
        self.show_status_thread.start()
        return
    
 
    def show_status_loop(self):
        self.logger.log ('show loop start',self.pause_at_end)
        while True:
            if self.quit_show_signal is True:
                self.quit_show_signal= False
                self.player.stop()
                self.state='idle'
                #print (self.state)
                return
            position=self.player.get_time()
            #self.logger.log ('track time',position)
            if self.pause_at_end == 'yes':
                if position > self.length - 100:   # 50 magic number )-:
                    self.pause_on()
                    self.logger.log ('paused at end ',position)
                    self.state='show-pauseatend'
                    #print (self.state)
                    return
                elif self.player.get_state() == vlc.State.Ended:
                    self.player.stop()
                    self.logger.log ('paused at end FAIL',position)
                    self.state='show-niceday'
                    self.player.stop()
                    #print (self.state)
                    return                    
                else:
                    time.sleep(0.01)
            else:
                if self.pause_at_end == 'no':
                    if self.player.get_state() == vlc.State.Ended:
                        self.player.stop()
                        self.logger.log ('ended with no pause at ',position)
                        #nice-day
                        self.state='show-niceday'
                        #print (self.state)
                        return
                    else:
                        time.sleep(0.01)
                else:
                    self.logger.log( 'illegal pause at end')

# ***********************
# Commands
# ***********************
        
    def get_state(self):
        return self.state

    def pause_on(self):
        self.player.set_pause(True)
        
    def pause_off(self):
        self.player.set_pause(False)
        
    def set_volume(self,volume):
        self.player.audio_set_volume(volume)

    def quit(self):
        self.quit_load_signal=True
        self.quit_show_signal=True
        if self.load_status_thread != None:
            self.load_status_thread.join()
        if self.show_status_thread != None:
            self.show_status_thread.join()
        self.player=None
        self.vlc_instance=None

     
class  Logger(object): 

    log_file=''
    start_time=0
# -------------------------------
# logging - log-file opened in init
# ------------------------------- 

    def init(self):
        self.work_dir=sys.path[0]
        Logger.log_file=open(self.work_dir+'/driver_log.txt','w')
        Logger.start_time=time.time()
        return 


    def log(self,*args):
        #return
        al=[]
        for arg in args:
            string_arg=str(arg)
            al.append(string_arg)
        text=' '.join(al)
        #.strftime("%A %d %B %Y %I:%M:%S%p")
        time_str="{:.6f}".format(time.time()-Logger.start_time)
        #print(time_str,text)
        Logger.log_file.write(time_str+ '     ' + text + '\n')
        Logger.log_file.flush()

    def close(self):
        Logger.log_file.close()


class CLI(object):

    def __init__(self):
        self.logger=Logger()
        self.logger.init()
        self.work_dir=sys.path[0]
        self.vv=VideoPlayer()

    def cli_loop(self):
        print ('VLCDriver starting')
        while True:
            cmd= input()
            self.do_command(cmd)
        
    def do_command(self,cmd):
        if cmd !='t':
            self.logger.log ('Command: ',cmd)
        if cmd=='restart':
            # test purposes only
            self.vv.quit()
            self.vv=None
            self.logger.close()
            self.logger=None
            self.__init__()
            self.cli_loop()
        elif cmd == 't':
            print (self.vv.get_state())
        elif cmd == 'l':
            self.vv.load()
        elif cmd== 's':
            self.vv.show()
        elif cmd == 'q':
            self.vv.quit()
            self.logger.close()
            exit(0)
        elif cmd=='p':
            self.vv.pause_on()
        elif cmd=='u':
            self.vv.pause_off()
        else:
            cmd_bit, parameters = cmd.split(' ', 1)
            #print (cmd_bit,parameters)
            if cmd_bit=='iopts':
                self.vv.instance_options=' '+parameters
                #self.logger.log ('iopts: ',parameters)
            elif cmd_bit=='track':
                self.vv.track_path=parameters
                self.logger.log ('track: ',parameters)
            elif cmd_bit=='pauseopts':
                self.vv.pause_at_start,self.vv.pause_at_end=parameters.split(' ')
                #self.logger.log ('pauseopts: ',parameters)
            elif cmd_bit=='ratio':
                self.vv.aspect_ratio = parameters
                #self.logger.log ('ratio: ',parameters)
            elif cmd_bit=='crop':
                self.vv.crop=parameters
                #self.logger.log ('crop: ',parameters)
            elif cmd_bit=='vol':
                self.vv.set_volume(int(parameters))
                #self.logger.log ('vol: ',parameters)
            else:
                print ('bad-command')



if __name__ == '__main__':    
    cc=CLI()
    cc.cli_loop()



  
    

    

