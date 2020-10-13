import time
import sys
import vlc #sudo pip3 install python-vlc
from tkinter import Tk, StringVar,Frame,Label,Button,Scrollbar,Listbox,Entry,Text
from tkinter import Y,END,TOP,BOTH,LEFT,RIGHT,VERTICAL,SINGLE,NONE,NORMAL,DISABLED

class VideoPlayer(object):
    
    # used first time and for every other instance
    def __init__(self,root):
        self.logger=Logger()
        self.logger.log('init VLC instance')
        self.root=root  #use tkinter for timers
        self.loop_timer=None



    # track,display,x,y,width,height,(pause at start = before,after,no),loaded callback
    def load(self, track,display, video_x,video_y,width,height,audio_device,pause_at_start,loaded_callback):
        self.loaded_callback=loaded_callback
        self.pause_at_start=pause_at_start
        
        audio_opt=self.parse_audio_device(audio_device)
    
        subtitle_opt=' --no-spu '
        #subtitle_opt = ''
        
        rotate_opt = ' --mmal-vout-transform 90  '   #auto, 0, 90, 180, 270, hflip, vflip, transpose, antitranspose
        rotate_opt=''
        
        video_title_opt = ' --no-video-title-show '
        
        window_opt= ' --mmal-vout-window=200*200+100+100 --mmal-vout-transparent '
        
        # options seem to apply to a VLC instance.
        # i_opts=(' --no-xlib --vout mmal_vout --mmal-layer=1 --mmal-display=' + display + rotate_opt + audio_opt + subtitle_opt + video_title_opt + window_opt )

        i_opts=('--no-xlib --vout mmal_vout --mmal-layer=1 --mmal-vout-window 400x300+0+0 --no-mmal-vout-transparent --mmal-display=' + display + ' ')

        
        # what is a mediaplayer ????
        p_opts= ('')
        self.logger.log(i_opts)
        
        # creating a vlc instance        
        self.vlc_instance = vlc.Instance(i_opts)
        
        #print ('devices',self.vlc_instance.audio_output_enumerate_devices())
        # print(self.vlc_instance.audio_output_device_list_get('alsa'))
        # get the media and obtain its length
        self.media = self.vlc_instance.media_new(track)
        self.media.parse()
        self.length=self.media.get_duration()
        self.logger.log ('track length',self.length)
        
        self.player = vlc.MediaPlayer(self.vlc_instance,'',p_opts)
        self.player.set_media(self.media)
        self.player.set_fullscreen(True)
        self.player.play()

        # audio starts before video shows on screen so mute until later
        self.logger.log ('mute sound')
        #self.player.audio_set_volume(0)
        self.player.audio_set_mute(True)
        
        # try and asign the background black to a Tkinter window - does not work
        #print ('tkinter top level', self.root.frame())       
        #self.player.set_xwindow( self.root.frame())
        #print ('x window',self.player.get_xwindow())        

        
        #calculate position for pause at start
        if self.pause_at_start=='before':
            # before first frame, pause when first 0 get_time() report is revived
            self.load_pause_position=-1
        elif self.pause_at_start=='after':
            # after first frame, when get_time() >0 allowing for sampling rate.
            self.load_pause_position = 200
        else:
            # no pause  - arbitrary large number - probably not used in PP.
            self.load_pause_position=1000000000
        

        #monitor the loading of the track using tkinter timer so can wait in a non_busy loop
        self.root.after(1,self.load_status_loop)
        
        #meanwhile make the Tkinter window appear above VLC's black background x window so that keys work.        
        self.root.iconify()
        self.root.update()
        self.root.after(1000, lambda: self.root.deiconify())
        return



    def load_status_loop(self):
        # wait until the load is complete
        position=self.player.get_time()
        if position > self.load_pause_position: #milliseconds
            if self.pause_at_start != 'no':
                self.pause_on()
                self.logger.log ('load paused at ',position)
                self.loaded_callback()
            else:
                self.logger.log ('load complete no pause')
                self.loaded_callback()
                return
        else:
            self.loop_timer=self.root.after(10,self.load_status_loop)


    def show(self,pause_at_end,previous,end_callback):
        self.previous_player=previous
        self.pause_at_end=pause_at_end
        self.end_callback=end_callback
        self.pause_off()
        self.logger.log ('pause off, start showing and wait for start')
        # wait for track to start player.get_time() reports 0 for a while then a positive number.
        # to stop two videos appearing at once and to also minimise the gap it is necessary to 
        # quit the previous video a few time reports before the first non-zero time report.
        # the wait_count threshold is going to be a guess.
        self.wait_count = 0
        self.root.after(1,self.wait_for_start)
        
    def wait_for_start(self):
        # wait until n zero reports at 10 mS have passed.  
        position=self.player.get_time()
        if self .wait_count <20:
            self.wait_count+=1
            self.root.after(10,self.wait_for_start)
        else:
            self.logger.log ('wait start finished with position',position)
            if self.previous_player !=None:
                self.previous_player.player.audio_set_mute(True)
            self.player.audio_set_mute(False)
            self.root.after(1,self.show_status_loop)
            self.root.after(1,self.finish_previous) 


        
    """
    # alternative, wait until position >0, this seems to produce flicker   
    def wait_for_start(self):
        position=self.player.get_time()
        self.logger.log ('wait start',position)
        if position <=0:
            self.root.after(10,self.wait_for_start)
        else:
            # first non-zero Position
            self.logger.log('detected first frame',position)
            #if self.previous_player !=None:
                #self.previous_player.player.audio_set_mute(True)
            self.player.audio_set_mute(False)
            self.root.after(2,self.show_status_loop)
            self.root.after(1,self.finish_previous)           
    """
    
    def finish_previous(self):
        if self.previous_player!=None:
            self.logger.log('Finish Previous')
            self.previous_player.player.stop()
 
            
    def show_status_loop(self):
        position=self.player.get_time()
        #self.logger.log ('track time',position)
        if self.pause_at_end == 'yes':
            if position > self.length - 300:   #milliseconds
                self.pause_on()
                if self.previous_player!=None:
                    self.previous_player.audio_set_volume(0)
                self.logger.log ('paused at end ',position)
                self.end_callback('pause_at_end')
            else:
                self.loop_timer=self.root.after(100,self.show_status_loop)
        else:
            if self.pause_at_end == 'no':
                if self.player.get_state() == vlc.State.Ended:
                    self.player.stop()
                    self.logger.log ('ended with no pause at ',position)
                    self.end_callback('nice_day')
                else:
                    self.loop_timer=self.root.after(100,self.show_status_loop)
            else:
                self.logger.log( 'illegal pause at end')

    def terminate(self):
        if self.loop_timer!=None:
            self.root.after_cancel(self.loop_timer)
        self.vlc_instance=None

# ***********************
# Commands
# ***********************

    def pause_on(self,event=None):
        self.player.set_pause(True)
        
    def pause_off(self,event=None):
        self.player.set_pause(False)

    def quit(self,event=None):
        self.player.stop()


    def parse_audio_device(self,audio):
        
        if audio in ('hdmi','hdmi0'):
            driver_option=' --aout=alsa --alsa-audio-device=plughw:b1,0 '
        elif audio == 'hdmi1':
            driver_option=' --aout=alsa --alsa-audio-device=plughw:b2,0 '
        elif audio == 'USB':
            driver_option=' --aout=alsa --alsa-audio-device=plughw:Device,0 '
        elif audio == 'A/V':
            driver_option=' --aout=alsa --alsa-audio-device=plughw:Headphones,0 '
        else:
            driver_option=''
        # self.logger.log('parse audio',driver_option)
        return driver_option

     
class  Logger(object): 

    log_file=''
    start_time=0
# -------------------------------
# logging - log-file opened in init
# ------------------------------- 

    def init(self):
        self.work_dir=sys.path[0]
        Logger.log_file=open(self.work_dir+'/log.txt','a')
        Logger.start_time=time.time()
        return 


    def log(self,*args):
        al=[]
        for arg in args:
            string_arg=str(arg)
            al.append(string_arg)
        text=' '.join(al)
        #.strftime("%A %d %B %Y %I:%M:%S%p")
        time_str="{:.6f}".format(time.time()-Logger.start_time)
        print(time_str,text)
        Logger.log_file.write(time_str+ '     ' + text + '\n')
        Logger.log_file.flush()

    def close():
        Logger.log_file.close()

# -------------------------------
# Test harness
# -------------------------------


class Shower(object):

    def __init__(self):

        self.logger=Logger()
        self.logger.init()
        
        self.work_dir=sys.path[0]

        # root is the Tkinter root widget
        self.root = Tk()
        self.root.title("VLC in Pi Presents Investigation")
        self.root.resizable(False,False)
        self.root.geometry("%dx%d%+d%+d"  % (1000,1000,100,100))

        # define response to main window closing
        self.root.protocol ("WM_DELETE_WINDOW", self.app_exit)
        
        # bind keys to play some combinations of tracks
        self.root.bind('<Escape>',self.app_exit)
        self.root.bind("1", self.play_show1) #just one track on HDMI-2
        self.root.bind("2", self.play_show2) # just one track on HDMI-1
        self.root.bind("3", self.play_show3) # two tracks on HDMI-2 with 'gapless' change :-)
        self.root.bind("4", self.play_show4) # two tracks on HDMI-2 with 'gappy' change        
        self.root.bind('5', self.play_show5) # two concurrent tracks, one on each display :-)
        self.root.bind("<Button-1>", self.mouse_click)
        
        #Init the VLC Driver - just init logging
        self.vp=VideoPlayer(self.root)

        
        # list of instances of VLC that have been used to play tracks
        self.vp_list=[]
        
        # and start Tkinter mainloop
        self.root.mainloop()

    def app_exit(self,event=None):
        # terminate all players
        for vp in self.vp_list:
            vp.terminate()
        self.root.destroy()
        self.logger.log ('vlcpy.py finished')
        exit()

    def mouse_click(self,event):
        self.logger.log ('mouse click at',event.x,event.y)


    def full_path(self,leaf):
        return self.work_dir+'/'+leaf


    # track 1 only
    def play_show1(self,event=None):
        self.logger.log ('start show1')
        self.od1=VideoPlayer(self.root)
        self.vp_list.append(self.od1)
        self.root.bind('u', self.od1.pause_off)
        self.root.bind('p', self.od1.pause_on)        
        self.root.bind('q', self.od1.quit) 
        # track,x,y,width,height,(pause at start = before,after,no),loaded callback
        self.od1.load(self.full_path('xthresh.mp4'),'HDMI-1',100,100,100,100,'hdmi0','before',self.loaded1_callback)

    def loaded1_callback(self):
        self.logger.log ('loaded 1')
        # (pause at end = yes,no), previous player, end callback
        self.od1.show('no',None,self.end1_callback)
        
    def end1_callback(self,status):
        self.logger.log ('ended 1',status)


    # track 2 only
    def play_show2(self,event=None):
        self.logger.log ('start show 2')
        self.od2=VideoPlayer(self.root)
        self.vp_list.append(self.od2)
        self.root.bind('u', self.od2.pause_off)
        self.root.bind('p', self.od2.pause_on)        
        self.root.bind('q', self.od2.quit) 
        
        # track,x,y,width,height,(pause at start = before,after,no),loaded callback
        self.od2.load(self.full_path('suits-short.mkv'),'HDMI-2',100,100,100,100,'A/V','before',self.loaded2_callback)

    def loaded2_callback(self):
        self.logger.log ('loaded 2')
        # (pause at end = yes,no), previous player, end callback
        self.od2.show('no',None,self.end2_callback)
        
    def end2_callback(self,status):
        self.logger.log ('ended 2',status)


    # play 2 tracks on HDMI-2 with 'gapless' transition
    def play_show3(self,event):
        # play first track normally
        self.logger.log ('start show 3')
        self.logger.log ('load 3')
        self.od3=VideoPlayer(self.root)
        self.vp_list.append(self.od3) 
        # track,x,y,width,height,(audio=hdmi0,hdmi1,A/V,USB),(pause at start = before,after,no),loaded callback
        self.od3.load(self.full_path('5sec.mp4'),'HDMI-2',100,100,100,100,'hdmi0','before',self.loaded3_callback)

    def loaded3_callback(self):
        self.logger.log ('loaded 3')
        # pause at end until next track is loaded.
        self.logger.log ('start showing 3')
        self.od3.show('yes',None,self.end3_callback)
        
    def end3_callback(self,status):
        self.logger.log ('end showing 3',status)
        if status == 'pause_at_end':
            self.logger.log ('pause at end so load 4')
            self.od4=VideoPlayer(self.root)
            self.vp_list.append(self.od4)
            self.od4.load(self.full_path('suits-short.mkv'),'HDMI-2',100,100,100,100,'hdmi0','before',self.loaded4_callback)
        else:
            #quit or nice_day, just return
            # by getting out of the callback
            self.logger.log ('ending 3  other than pause at end',status)
            self.root.after(1,self.finished)

    def loaded4_callback(self):
        self.logger.log ('loaded 4')
        self.logger.log ('start showing 4')        
        self.od4.show('no',self.od3,self.end4_callback)
        
    def end4_callback(self,status):
        self.logger.log ('end show 4',status)
        self.root.after(1,self.finished)
        
        
        
    # play 2 tracks on HDMI-2 with 'gappy' transition        
    def play_show4(self,event):
        # play first track normally
        self.logger.log ('start show 4')
        self.logger.log ('load 5')
        self.od5=VideoPlayer(self.root)
        self.vp_list.append(self.od5) 
        # track,x,y,width,height,(audio=hdmi0,hdmi1,A/V,USB),(pause at start = before,after,no),loaded callback
        self.od5.load(self.full_path('5sec.mp4'),'HDMI-2',100,100,100,100,'hdmi0','before',self.loaded5_callback)

    def loaded5_callback(self):
        self.logger.log ('loaded ')
        # no pause at end so a black gap is produced
        self.logger.log ('start showing 5')
        self.od5.show('no',None,self.end5_callback)
        
    def end5_callback(self,status):
        self.logger.log ('end showing 5',status)
        if status == 'pause_at_end':
            self.logger.log ('!!!!pause at end should not happen')
            # get out of the callback
            self.root.after(1,self.finished)
        else:
            self.logger.log ('ending 5  other than pause at end',status)
            self.logger.log ('loading 6')
            self.od6=VideoPlayer(self.root)
            self.vp_list.append(self.od6)
            self.od6.load(self.full_path('suits-short.mkv'),'HDMI-2',100,100,100,100,'hdmi0','before',self.loaded6_callback)


    def loaded6_callback(self):
        self.logger.log ('loaded 6')
        self.logger.log ('start showing 6')        
        self.od6.show('no',self.od5,self.end6_callback)
        
    def end6_callback(self,status):
        self.logger.log ('end show 4',status)
        self.root.after(1,self.finished)

        
    # play 2 tracks concurrently
    def play_show5(self,event):
        self.logger.log ('start show 5')
        self.play_show1()
        self.play_show2()
        
    def finished(self):
        self.logger.log ('finished')
        return
    
    
if __name__ == '__main__':    
    ss=Shower()
 

