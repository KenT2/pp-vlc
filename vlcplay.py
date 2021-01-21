"""
    VideoPlayer() is a prototype for pp_vlcplayer.py in Pi Presents
    
    #GUI() is a simple Tkinter gui interface for exercising VideoPlayer()
        commands:
        1,2,3,4,5 play some shows - see GUI() code for details
        p - pause
        u - unpause
        + - inc volume
        - - dec volume
        q - quit track
        escape - exit app
        
    CLI()
    command line utility to test vlcdriver.py and the pexpect communication with it
    see CLI() code for commands

    choose CLI or GUI from __main__
"""

import pexpect
import subprocess
import time,sys
import copy
from tkinter import *



# **************************
# prototype for pp_vlcplayer.py in Pi Presents
# class is instantiated once and once only for each track
# **************************

class VideoPlayer(object):
    
    def __init__(self,widget):
        self.root=widget
        #self.logger=Logger()
        #self.logger.init()
        self.work_dir=sys.path[0]
        cmd= 'DISPLAY= python3 '+ self.work_dir+'/vlcdrive.py'
        #print (cmd)
        # need bash because of DISPLAY=
        self.vlcdrive = pexpect.spawn('/bin/bash', ['-c', cmd],encoding='utf-8')
        # get rid of driver start message
        print('\n\nDriver Start Message: ',self.vlcdrive.readline())
        self.vlcdrive.setecho(False)
        

    def load(self,track,track_params,load_callback):
        self.load_callback=load_callback
        iopts,pauseopts,aspectopt,cropopt=self.process_params(track_params)
        #print ('iopts'+iopts)
        #print ('pauseopts'+popts)
        self.vlcdrive.sendline('iopts'+iopts)
        self.vlcdrive.sendline('pauseopts'+pauseopts)
        if cropopt.strip(' ')!= '':
                self.vlcdrive.sendline('crop '+ cropopt)
        if aspectopt.strip(' ')!= '':
                self.vlcdrive.sendline('ratio '+ aspectopt)
        track_path=self.work_dir+'/'+track
        self.vlcdrive.sendline('track '+track_path)
        self.vlcdrive.sendline('l')
        self.root.after(1,self.load_loop)
        
    def load_loop(self):
        resp=self.get_state()
        # driver changes state from load-loading when track is paused at start.
        # ???? what if no pause
        if resp in ('load-ok','load-fail','idle'):
            print ('     End load with : '+resp)
            self.load_callback(resp)
            return
        else:
            self.root.after(10,self.load_loop)

    def show(self,show_callback):
        self.show_callback=show_callback
        self.set_volume(self.volume)
        self.vlcdrive.sendline('s')
        self.root.after(1,self.show_loop)
                
    def show_loop(self):
        resp=self.get_state()
        # driver changes state from show-showing depending on freeze-at-end.
        if resp in ('show-pauseatend','show-niceday','idle','show-fail'):
            print ('     End show with: ' + resp)
            self.show_callback(resp)
            return
        else:
            self.root.after(10,self.show_loop)
        
    def pause_on(self):
        self.vlcdrive.sendline('p')
        
    def pause_off(self):
        self.vlcdrive.sendline('u') 

    def set_volume(self,vol):
        self.vlcdrive.sendline('vol '+ str(vol))
        
    def inc_volume(self):
        if self.volume < self.max_volume:
            self.volume+=1
        self.set_volume(self.volume)
        
    def dec_volume(self):
        if self.volume > 0:
            self.volume-=1
        self.set_volume(self.volume)

    def close(self):
        self.quit()
        print ('     Done close (quit)')
        
    def quit(self):
        #send quit to driver
        self.vlcdrive.sendline('q')
        # and terminate the vlcdriver process through pexpect
        self.vlcdrive.terminate()
        #self.root.after(1,self.wait_for_idle)
        
    def wait_for_idle(self):
        if self.get_state()=='idle':
            print ('Idle after quit')  
            self.vlcdrive.terminate()
            return
        print ('wait for idle')
        self.root.after(10,self.wait_for_idle)   
      

    def get_state(self):
        self.vlcdrive.sendline('t')
        resp=self.vlcdrive.readline().strip('\r\n')
        #print (resp)
        return resp


    def process_params(self,track_params):
            
        # volume set during show by set_volume()
        # --------------------------------------
        #volume
        self.max_volume=int(track_params['vlc-max-volume'])
        self.volume=int(track_params['vlc-volume'])
        self.volume=min(self.volume,self.max_volume)

        # instance options
        # ----------------
        #audio device
        if track_params['vlc-audio-device']=='':
            # default from task bar
            audio_opt= '--aout=pulse '
        else:
            # how do you select a pulseaudio sink in vlc?
            audio_opt=''
        
        # subtitles
        if track_params['vlc-subtitles']=='yes':
            subtitle_opt = ' '
        else:
            subtitle_opt='--no-spu '

        # transformation
        if track_params['vlc-transform'] !='':
            transform_opt = '--mmal-vout-transform='+track_params['vlc-transform']+' '
            #auto, 0, 90, 180, 270, hflip, vflip, transpose, antitranspose
        else:
            transform_opt=''
        
        #transparency
        if track_params['vlc-transparent']=='yes':
            transparent_opt= '--mmal-vout-transparent '
        else:
            transparent_opt=' '
            
        #display
        display_opt='--mmal-display='+track_params['vlc-display-name']+' '
        # does it do DSI-1????
        
        #layer
        layer_opt='--mmal-layer='+track_params['vlc-display-layer']+' '
        
        
        # window    
        window_opt= '--mmal-vout-window '+track_params['vlc-window']+' '

        other_opts= ' '+track_params['vlc-other-options']+' '

        iopts=' '+window_opt+layer_opt+display_opt+transparent_opt+transform_opt+subtitle_opt +audio_opt + other_opts

        
        # player run time options
        #-------------------------
        
        #aspect ratio
        if track_params['vlc-aspect-ratio'] !='':
            aspect_opt= track_params['vlc-aspect-ratio']
        else:
            aspect_opt=''

        #crop
        if track_params['vlc-crop'] !='':
            crop_opt= track_params['vlc-crop']
        else:
            crop_opt=''
        
        # pause options
        #---------------
        freeze_start_opt=' '+track_params['vlc-freeze-at-start']
        freeze_end_opt=' '+track_params['vlc-freeze-at-end']
        
        pauseopts= freeze_start_opt+freeze_end_opt
        
        return iopts,pauseopts,aspect_opt,crop_opt





class GUI(object):
    def __init__(self):
        #self.logger=Logger()
        #self.logger.init()
        self.root = Tk()
        self.root.title("VLC in Pi Presents Investigation")
        self.root.resizable(False,False)
        self.root.geometry("%dx%d%+d%+d"  % (200,200,100,400))
        # define response to main window closing
        self.root.protocol ("WM_DELETE_WINDOW", self.app_exit)
        self.root.bind('<Escape>',self.app_exit)
        self.root.bind("1", self.play_show1) #just one track on HDMI-1
        self.root.bind("2", self.play_show2) # just one track on HDMI-1
        self.root.bind("3", self.play_show3) # two tracks on HDMI-2 with 'gapless' change
        self.root.bind("4", self.play_show4) # two tracks on HDMI-2 with 'gappy' change        
        self.root.bind('5', self.play_show5) # two concurrent tracks show1 and show2
        self.root.bind("<Button-1>", self.mouse_click)
        
        # list of instances of VLC that have been used to play tracks
        self.vp_list=[]
        self.default_track_params={
            'vlc-audio-device':'',  # pulseaudio device, must be blank as do not know how to select sink in vlc
           'vlc-volume':'100','vlc-max-volume':'100',      #initial volume for track and max volume when using the volume control
           'vlc-other-options':'',  # other VLC instance options separated by spaces
           'vlc-display-name':'HDMI-1',  # display
           'vlc-display-layer':'1',      # layer
           'vlc-transparent':'yes',   #whether the display around the video is transparent or not (black)  yes/no
           'vlc-subtitles':'no',   # use subtitles yes/no
           'vlc-transform':'',          #transformation auto,0, 90,180, 270, hflip, vflip, transpose, antitranspose

        # Cannot use both crop and aspect ratio
        # window size w*h needs to have the same ratio as the result of crop or aspect-ratio 
           'vlc-crop':'',               #<aspect_num>:<aspect_den> e.g.4:3
                                        #<width>x<height>+<x>+<y>
                                        #<left>+<top>+<right>+<bottom>
          'vlc-aspect-ratio':'',        # aspect ratio 4:3  or 1.25
          'vlc-window':'400x300+0+0',   #window in which to display video. fullscreen or wxh+x+y
          
          
           # non-vlc options
           'vlc-freeze-at-start':'before', # pause before or after first frame  before/after/no?
           'vlc-freeze-at-end':'yes',  # pause playing just before final frame, used for 'gapless' showing  yes/no
           'vlc-pause-timeout':'0',    # timeout for any user initiated pause during playing

           'vlc-duration':'0'        #duration of track, mainly for images.
               }
        self.root.mainloop()
        
    def app_exit(self,event=None):
        # terminate all players
        for vp in self.vp_list:
            vp.quit()
        self.root.destroy()
        print('vlcplay.py finished')
        exit()


    # respond to Tkinter callbacks getting rid of event
        
    def state(self,event=None):
        # test only
        print(self.player.get_state())
        
    def pause_on(self,event=None):
        self.player.pause_on()

    def pause_off(self,event=None):
        self.player.pause_off()

    def quit(self,event=None):
        self.player.quit()
        
    def inc_volume(self,event=None):
        self.player.inc_volume()
        
    def dec_volume(self,event=None):
        self.player.dec_volume()

    def mouse_click(self,event):
        print('mouse click at',event.x,event.y)


# *****************************
# shows - a show is a sequence of tracks
# *****************************

   # one track on HDMI-1
    def play_show1(self,event=None):
        self.track_params=copy.deepcopy(self.default_track_params)
        self.track_params['vlc-subtitles']='yes'
        self.track_params['vlc-display-name']='HDMI-1'
        self.track_params['vlc-display-layer']='2'
        self.track_params['vlc-window']= '800x600+200+200'
        self.track_params['vlc-freeze-at-start']='before'
        self.track_params['vlc-freeze-at-end']='yes'
        self.track_params['vlc-volume']='50'
        #self.track_params['vlc-crop']='1:1'
        #self.track_params['vlc-transform']='vflip'
        #self.track_params['vlc-aspect-ratio']='4:3'
        self.od1=VideoPlayer(self.root)
        self.player=self.od1
        self.vp_list.append(self.od1)
        self.root.bind('u', self.pause_off)
        self.root.bind('p', self.pause_on)        
        self.root.bind('q', self.quit)
        self.root.bind('t', self.state)
        self.root.bind('+', self.inc_volume)
        self.root.bind('-', self.dec_volume)
        print ('load track 1')
        self.od1.load('xthresh.mp4',self.track_params,self.loaded1_callback)
        return
        

        
    def loaded1_callback(self,state):
        print ('Loaded 1: ', state)
        if state != 'load-ok':
            print ('Load 1 failed', state)
            return
        self.od1.show(self.show1_callback)
        return

    def show1_callback(self,state):
        print ('shown 1: ', state)
        if state != 'show-pauseatend':
            self.od1.close()
        else:
            self.root.after( 5000,self.od1.close)
            

   # one track on HDMI-1
    def play_show2(self,event=None):
        self.track_params=copy.deepcopy(self.default_track_params)
        self.track_params['vlc-subtitles']='yes'
        self.track_params['vlc-display-name']='HDMI-1'
        self.track_params['vlc-display-layer']='1'
        self.track_params['vlc-freeze-at-start']='before'
        self.track_params['vlc-freeze-at-end']='yes'
        self.track_params['vlc-window']= '1600x900+00+00' # 'fullscreen'
        #self.track_params['vlc-crop']= '4:3'
        #self.track_params['vlc-aspect-ratio']= '1920:1080'
        self.od2=VideoPlayer(self.root)
        self.player=self.od2
        self.vp_list.append(self.od2)
        self.root.bind('u', self.pause_off)
        self.root.bind('p', self.pause_on)        
        self.root.bind('q', self.quit)
        self.root.bind('t', self.state)
        print ('load track 2')
        self.od2.load('suits-short.mkv',self.track_params,self.loaded2_callback)
        return
        

        
    def loaded2_callback(self,state):
        print ('Loaded 2: ', state)
        if state != 'load-ok':
            print ('Load 2 failed', state)
            return
        self.od2.show(self.show2_callback)
        return

    def show2_callback(self,state):
        print ('shown 2: ', state)
        if state != 'show-pauseatend':
            self.od2.close()
        else:
            self.root.after( 2000,self.od2.close)


    # play 2 tracks on HDMI-1 with 'gapless' transition
    def play_show3(self,event):
        self.track_params=copy.deepcopy(self.default_track_params)
        self.track_params['vlc-display-name']='HDMI-1'
        self.track_params['vlc-freeze-at-start']='before'
        self.track_params['vlc-freeze-at-end']='yes'
        self.track_params['vlc-window']='800x600+0+0'
        self.root.bind('u', self.pause_off)
        self.root.bind('p', self.pause_on)        
        self.root.bind('q', self.quit)
        self.root.bind('t', self.state)
        # play first track normally
        print('Start Show 3')
        print('load track 3')
        self.od3=VideoPlayer(self.root)
        self.player=self.od3
        self.vp_list.append(self.od3)
        self.od3.load('5sec.mp4',self.track_params,self.loaded3_callback)


    def loaded3_callback(self,state):
        print ('Loaded 3: ', state)
        if state != 'load-ok':
            print ('Load failed', state)
            return
        print('show track 3')
        self.od3.show(self.show3_callback)
        return
        
    def show3_callback(self,state):
        print ('shown 3:', state)
        if state != 'show-pauseatend':
            print ('Fail, not pause at end')
            self.od3.close()
        else:
            print('load track 4')
            self.od4=VideoPlayer(self.root)
            self.vp_list.append(self.od4)
            self.player=self.od4
            self.track_params=copy.deepcopy(self.default_track_params)
            self.track_params['vlc-window']='800x600+0+0'
            self.track_params['vlc-display-name']='HDMI-1'
            self.track_params['vlc-freeze-at-start']='before'
            self.track_params['vlc-freeze-at-end']='yes'
            self.od4.load('5sec.mp4',self.track_params,self.loaded4_callback)


    def loaded4_callback(self,state):
        print('loaded 4: ',state)
        print('show 4')
        self.od4.show(self.show4_callback)
        print('close 3')
        self.od3.close()

                
    def show4_callback(self,state):
        print ('shown 4: ',state)
        self.root.after( 2000,self.od4.close)
        

    # play 2 tracks on HDMI-1 with 'gappy' transition
    def play_show4(self,event):
        self.track_params=copy.deepcopy(self.default_track_params)
        self.track_params['vlc-display-name']='HDMI-1'
        self.track_params['vlc-freeze-at-start']='before'
        self.track_params['vlc-freeze-at-end']='no'
        self.track_params['vlc-window']='800x600+0+0'
        self.root.bind('u', self.pause_off)
        self.root.bind('p', self.pause_on)        
        self.root.bind('q', self.quit)
        self.root.bind('t', self.state)
        # play first track with freeze at end off
        print('Start Show 4')
        print('load track 5')
        self.od5=VideoPlayer(self.root)
        self.player=self.od5
        self.vp_list.append(self.od5)
        self.od5.load('5sec.mp4',self.track_params,self.loaded5_callback)


    def loaded5_callback(self,state):
        print ('Loaded 5: ', state)
        if state != 'load-ok':
            print ('Load failed', state)
            return
        print('show track 5')
        self.od5.show(self.show5_callback)
        return
        
    def show5_callback(self,state):
        print ('shown 5:', state)
        if state != 'show-niceday':
            print ('Fail, not niceday')
        else:
            print('load track 6')
            self.od6=VideoPlayer(self.root)
            self.vp_list.append(self.od6)
            self.player=self.od6
            self.track_params=copy.deepcopy(self.default_track_params)
            self.track_params['vlc-window']='800x600+0+0'
            self.track_params['vlc-display-name']='HDMI-1'
            self.track_params['vlc-freeze-at-start']='before'
            self.track_params['vlc-freeze-at-end']='yes'
            self.od6.load('5sec.mp4',self.track_params,self.loaded6_callback)


    def loaded6_callback(self,state):
        print('loaded 6: ',state)
        print('show 6')
        self.od6.show(self.show6_callback)


    def show6_callback(self,state):
        print ('shown 6: ',state)
        self.root.after( 2000,self.od6.close)

        
    # play 2 tracks concurrently
    def play_show5(self,event):
        print('start show 5')
        self.play_show1()
        self.play_show2()
        
"""
# Tests vlcdriver and the pexpect interface by
# allowing commands to be sent by the user
# commands are as in vlcdriver.py without Return

# PP would call _init_ load,show, and close/quit 
# If no parameters are sent using iopts and pauseopts aspectopt cropopt commands then the defaults in vlcdrive.py are used
# track must be the full path to file. If no track command is sent then the default track in vlcdrive.py is used
"""
            
class CLI(object):
    
    def __init__(self):
        #self.logger=Logger()
        #self.logger.init()
        self.work_dir=sys.path[0]
        # start the vlc driver which waits for commands
        cmd= 'DISPLAY= python3 '+ self.work_dir+'/vlcdrive.py'
        # need bash because of DISPLAY=
        self.vlcdrive = pexpect.spawn('/bin/bash', ['-c', cmd],encoding='utf-8')
        
        # print the start message read from the driver
        print('Start Message: '+self.vlcdrive.readline())
        #stop pexpect echoing the command
        self.vlcdrive.setecho(False) 

        while True:
            x=input('>:')
            self.do_command(x)
        
    def do_command(self,cmd):
        if cmd == 't':
            # print state of track playing
            self.vlcdrive.sendline('t')
            print(self.vlcdrive.readline(),end="")
            
        elif cmd in ('l','s','p','u'):
            self.vlcdrive.sendline(cmd)
            
        elif cmd == 'q':
            self.vlcdrive.sendline('q')            
            #self.logger.close()
            exit(0)
        else:
            cmd_bit, parameters = cmd.split(' ', 1)
            #print (cmd_bit,parameters)
            if cmd_bit in ('iopts','pauseopts','track','vol','ratio','crop'):
                self.vlcdrive.sendline(cmd) 
            else:
                print ('bad command')

# -------------------------------
# Logger  - log stuff to player_log.txt
# ------------------------------- 
     
class  Logger(object): 

    log_file=''
    start_time=0


    def init(self):
        self.work_dir=sys.path[0]
        Logger.log_file=open(self.work_dir+'/player_log.txt','a')
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

# -------------------------------
# main programs
# ------------------------------- 

if __name__ == '__main__':
    # gui interface which is a prototype for pp_vlcplayer.py in Pi Presents
    cc=GUI()
    
    # command line utility to test vlcdriver and pexpect interface  
    #cc=CLI()

