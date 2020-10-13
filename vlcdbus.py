import dbus
import subprocess
import signal
import re
import time
import os
import sys
import shlex
import vlc #sudo pip3 install python-vlc
import stylize #sudo pip3 install stylize
from tkinter import Tk, StringVar,Frame,Label,Button,Scrollbar,Listbox,Entry,Text
from tkinter import Y,END,TOP,BOTH,LEFT,RIGHT,VERTICAL,SINGLE,NONE,NORMAL,DISABLED
from datetime import datetime, timezone

class VLCDriver(object):
    
    _trackMap = {
        'trackid': 'mpris:trackid',
        'length': 'mpris:length',
        'artUrl': 'mpris:artUrl',
        'album': 'xesam:album',
        'artist': 'xesam:artist',
        'title': 'xesam:title',
        'url': 'xesam:url',
        'rating': 'xesam:autoRating',
        'status': 'PlaybackStatus',
        'position':'Position'
    }
    
    start_time=0
    vlc_template = ['DISPLAY= ','cvlc', '-I', 'dummy', '--control', 'dbus']
    
    notrack='/org/mpris/MediaPlayer2/TrackList/NoTrack'
    
    
    def init(self):
        VLCDriver.start_time=time.time()
        self.log_file=open('/home/pi/dbusvlc/log.txt','a')
        self.log('--init--')
        # run once at power on because dbus seems to need VLC player instance running first
        vlc_cmd = VLCDriver.vlc_template
        self.log ('Initialise VLCPlayer',vlc_cmd)
        cmd=' '.join(vlc_cmd)
        print (cmd)
        #split=shlex.split(cmd)
        #print (split)
        self._process=subprocess.Popen(cmd,shell=True,stdout=open('/dev/null','a'),stderr=open('/dev/null','a'))
        self.pid=self._process.pid
        self.log ('VLC launched, pid: ',self.pid,'\n\n')
        return self.pid
        
        
    # used first time and for every other instance
    def __init__(self,root):
        self.work_dir=sys.path[0]
        self.log_file=open(self.work_dir+'/log.txt','a')
        self.log('--init track instance--')
        self.root=root  #use tkinter for timers
        self.loop_timer=None
        self.iface_player=None
        self.iface_root=None
        self.iface_props=None
        self.mediaplayer = 'org.mpris.MediaPlayer2.vlc.instance'
        self.mediaplayer_path='/org/mpris/MediaPlayer2'
        self.t_process=None

    # track,display,x,y,width,height,(pause at start = before,after,no),loaded callback
    def load(self, track,display, video_x,video_y,width,height,pause_at_start,loaded_callback):
        self.loaded_callback=loaded_callback
        self.pause_at_start=pause_at_start
        #calculate position for pause at start
        if self.pause_at_start=='before':
            self.load_pause_position=-1
        elif self.pause_at_start=='after':
            self.load_pause_position = 200000
        else:
            # arbitrary large number
            self.load_pause_position=1000000000

        #prepare command for VLC

        tvlc_template = ['cvlc', '-I', 'dummy', '--control', 'dbus']
        #tvlc_template = ['cvlc' ,'-I', 'dummy', '--control', 'dbus']
        cvlc_cmd=['cvlc']
        window_opt= ['--mmal-vout-window=200x200+100+100']
        trans_opt = ['--mmal-vout-transparent']
        video_x_str=   ['--video-x=0'] 
        video_y_str=   ['--video-y=0']
        width= ['--width=10']
        height= ['--height=10']
        vout_cmd = ['-V']
        mmal_val = ['mmal_vout']
        mmal_display= ['--mmal-display='+display]
        mmal_layer= ['--mmal-layer=1']
        background = ['--no-video-deco'] #does nothing
        fullscreen=['--no-qt-video-autoresize']
        title = ['--no-video-title-show']
        tfile = [track]

        vlc_cmd=tvlc_template + vout_cmd + mmal_val + mmal_display + mmal_layer + fullscreen\
         + background + title + window_opt + trans_opt + video_x_str + video_y_str + width+height
        cmd=' '.join(vlc_cmd)
        self.log ('New instance created to play a track\n',cmd,'\n')

        #xcmd='cvlc -I dummy --control dbus --vout mmal_vout --mmal-display=HDMI-1 --mmal-layer=1 -f --no-video-deco --no-video-title-show --mmal-vout-window=200x200+100+100 --mmal-vout-transparent '
        #split = shlex.split(xcmd)
        #print (split)

        #self.t_process=subprocess.Popen('./vlctrack.sh',shell=True) #lots of debug from VLC
        self.t_process=subprocess.Popen(vlc_cmd,shell=False) #lots of debug from VLC
        #self.t_process=subprocess.Popen(vlc_cmd,shell=False,stdout=open('/dev/null','a'),stderr=open('/dev/null','a'))
        self.t_pid=self.t_process.pid
        print ('after open',self.t_process.pid)
        self.setup_dbus()

        uri='file://'+self.work_dir+ '/'+ track
        self.log ('Open URI - '+uri)
        self.iface_player.OpenUri(uri)
        #self.setup_dbus()
        #get the duration of the track, using tkinter timer so can wait in a non_busy loop
        self.root.after(1,self.wait_for_length)
        
        # bodge to make the window appear above the black fullscreen x window created by VLC
        
        #self.root.lift()
        #self.root.attributes("-topmost",True)
        #self.root.after(1, lambda: self.root.focus_force())
        
        #get the Tkinter window above the black screen so that keys work.        
        #self.root.iconify()
        #self.root.update()
        #self.root.after(1000, lambda: self.root.deiconify())
        
        #self.root.deiconify()
        #self.root.focus_force()
        return

    def wait_for_length(self):
        success,length=self.get_metadata_item('mpris:length')
        if success!= True:
            self.log ('waiting to get duration, try again')
            self.root.after(10,self.wait_for_length)
        if length > 0:
            self.length=length
            self.log ('Duration: ',self.length)
            # start the loop that reads position and compares pause at start
            self.loop_timer=self.root.after(1,self.load_status_loop)
        else:
            #self.log ('Length less than zero',length)
            self.root.after(10,self.wait_for_length)

    def load_status_loop(self):
        success,position=self.get_property('Position')
        if success != True:
            self.log ('Fail Get Load Position')
            return
        #self.log (str(position))
        if position > self.load_pause_position: #microseconds
            if self.pause_at_start != 'no':
                # audio starts before video shows on screen so kill until later
                #self.set_volume(-60)
                self.pause_on()
                self.log ('load paused at ',position)
                self.loaded_callback()
            else:
                self.set_volume(-60)
                self.log ('load complete no pause')
                self.loaded_callback()
                return
        else:
            self.loop_timer=self.root.after(10,self.load_status_loop)


    def show(self,pause_at_end,previous,end_callback):
        self.previous_player=previous
        self.pause_at_end=pause_at_end
        self.end_callback=end_callback
        self.log('before pause off')
        self.pause_off()
        self.log ('start show after pause off')
        # wait for track to start
        self.root.after(1,self.wait_for_start)
        
    def wait_for_start(self):
        success,position=self.get_property('Position')
        #self.log ('wait start',position)
        if position <=0:
            self.root.after(10,self.wait_for_start)
        else:
            # first non-zero Position
            self.log('detected first frame',position)
            self.root.after(1,self.show_status_loop)
            self.root.after(500,self.finish_previous)           
 
    def finish_previous(self):
        print ('set volume 0')
        self.set_volume(0)
        if self.previous_player!=None:
            self.log('Finish Previous')
            self.previous_player.stop('')
            #self.previous_player.pause_off() 
            
    def show_status_loop(self):
        success,position=self.get_property('Position')
        if success != True:
            # self.log ('Fail Get Show Position')
            self.end_callback('quit')
        else:
            #self.log ('position',str(position))
            if self.pause_at_end == 'yes':
                if position > self.length - 300000:   #microseconds
                    self.pause_on()
                    self.log ('paused at end ',position)
                    self.end_callback('pause_at_end')
                else:
                    self.loop_timer=self.root.after(100,self.show_status_loop)
            else:
                if self.pause_at_end == 'no':
                    if position == 0:   #microseconds
                        #self.pause_on()
                        self.log ('ended with no pause at ',position)
                        self.end_callback('nice_day')
                    else:
                        self.loop_timer=self.root.after(100,self.show_status_loop)
                else:
                    self.log( 'illegal pause at end')




# ***********************
# Commands
# ***********************

    def pause_on(self,event=None):
        self.iface_player.Pause()
        

    def pause_off(self,event=None):
        self.iface_player.Play()       

    def stop(self,event):
        self.iface_player.Stop()
        self.iface_root.Quit()
        self.t_process=None

    def terminate(self):
        if self.loop_timer!=None:
            self.root.after_cancel(self.loop_timer)
        if self.iface_player !=None:
            self.iface_player.Stop()
        if self.iface_root !=None:
            self.iface_root.Quit()
        self.t_process=None
        # self._process.terminate()

    # kill off omxplayer when it hasn't terminated at the end of a track.
    # send SIGINT (CTRL C) so it has a chance to tidy up daemons and omxplayer.bin
    def kill(self):
        #if self.is_running()is True:
        self._process.send_signal(signal.SIGINT)


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
# DBus veneer
# -------------------------------

    def set_volume(self,volume):
        millibels=volume*100
        out = pow(10, millibels / 2000.0)
        can=self.iface_props.Get('org.mpris.MediaPlayer2.Player','CanControl')
        print ('CanControl',can)
        #self.iface_props.Set('org.mpris.MediaPlayer2.Player', 'VolumeSet', dbus.Double(1.0))
        vol=self.iface_props.Get('org.mpris.MediaPlayer2.Player','Volume')
        print ('Volume',vol)
        #self.iface_props.Volume(1)
        #self.set_property('Volume',0.0)

        vol=self.iface_props.Get('org.mpris.MediaPlayer2.Player','Volume')
        print ('Volume after',vol)
        
    def set_property(self,prop,value):
        try:
            val = self.iface_props.Set('org.mpris.MediaPlayer2.Player',prop,dbus.Double(value))
            #self.log ('property',prop,val)
            return True,val
        except dbus.exceptions.DBusException as ex:
            self.log ('Failed set_property - dbus exception: {}'.format(ex.get_dbus_message()))
            return False,-1         
    
        
    def get_property(self,prop):
        try:
            val = self.iface_props.Get('org.mpris.MediaPlayer2.Player',prop)
            #self.log ('property',prop,val)
            return True,val
        except dbus.exceptions.DBusException as ex:
            self.log ('Failed get_property - dbus exception: {}'.format(ex.get_dbus_message()))
            return False,-1  


  # Get all availables information from DBus for a player object
    def get_metadata(self):
        self._info = {}
        try:
            metadata = self.iface_props.GetAll('org.mpris.MediaPlayer2.Player')
            for key, val in metadata.items():
                if isinstance(val, dict):
                    for subk, subv in val.items():
                        self._info[subk] = subv
                self._info[key] = val
            #self.print_metadata()
            return True,''
        except:
            return False, 'get_metadata failed'
    
    # Print information for a player
    def print_metadata(self):
        print ('\n\nmetadata')
        for k, v in self._trackMap.items():
            if v not in self._info:
                continue
            val = self._info[v]
            print (v,val)
            #print("{}: {}".format(', '.join(val) if isinstance(val, list) else val))
        print ('\n\nend')
    
    def get_metadata_item(self, key):
        success,message=self.get_metadata()
        if success is False:
            return False,message
        try:
            value = self._info[key]
            if isinstance(value, int):
                return True,value

            return True, ''.join(self._info[key])
        except KeyError:
            return False,key+' not found'

    def setup_dbus(self):
        self.mediaplayer_instance = self.mediaplayer + str(self.t_pid)
        self.log ('\nsetup dbus',self.t_pid,self.mediaplayer_instance)
        self.bus = dbus.SessionBus()
        self.bus_name=self.bus.get_unique_name()
        self.log ('bus name ',self.bus_name)
        
        self.dbus_connected=False
        self.player=self.wait_for_dbus()
               
        self.log ('player', self.player.bus_name,self.player.requested_bus_name)

        self.iface_player = dbus.Interface(self.player, dbus_interface='org.mpris.MediaPlayer2.Player')
        self.iface_props = dbus.Interface(self.player, dbus_interface="org.freedesktop.DBus.Properties")
        self.iface_root = dbus.Interface(self.player, dbus_interface="org.mpris.MediaPlayer2") 
    
    
    def wait_for_dbus(self):
        while True:
            try:
                player = dbus.SessionBus().get_object(self.mediaplayer_instance, self.mediaplayer_path, introspect=False)
                return player
            except dbus.exceptions.DBusException as ex:
                #print ('wait for dbus',ex)
                self.root.after(10,self.wait_for_dbus)


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
        self.root.geometry("%dx%d%+d%+d"  % (1000,1000,100,100))

        # define response to main window closing
        self.root.protocol ("WM_DELETE_WINDOW", self.app_exit)
        self.root.bind('<Escape>',self.app_exit)
        self.root.bind("1", self.play1)
        self.root.bind("2", self.play2)
        self.root.bind("3", self.play3)
        
        #Init the VLC Driver
        # init starts a dummy instance of VLC. Seems to be required to make DBUS work
        self.vlc=VLCDriver(self.root)
        self.vlc.init()
        
        # list of instances of VLC other than the initial dummy
        self.vlc_list=[]
        
        # and start Tkinter mainloop
        self.root.mainloop()

    def app_exit(self,event=None):
        # terminate all the track vlc's
        for vlcs in self.vlc_list:
            vlcs.terminate()
        # terminate the initial dummy vlc
        self.vlc.kill()
        self.root.destroy()
        exit()

    # track 1 only
    def play1(self,event):
        self.vlc.log ('play1')
        self.od1=VLCDriver(self.root)
        self.vlc_list.append(self.od1)
        self.root.bind('u', self.od1.pause_off)
        self.root.bind('p', self.od1.pause_on)        
        self.root.bind('q', self.od1.stop) 
        # track,x,y,width,height,(pause at start = before,after,no),loaded callback
        self.od1.load('5sec.mp4','HDMI-1',100,100,100,100,'before',self.loaded1_callback)

    def loaded1_callback(self):
        self.vlc.log ('loaded 1')
        # (pause at end = yes,no), end callback
        self.od1.show('no',None,self.end1_callback)
        
    def end1_callback(self,status):
        self.vlc.log ('ended 1',status)


    # track 2 only
    def play2(self,event):
        self.vlc.log ('play 2')
        self.od2=VLCDriver(self.root)
        self.vlc_list.append(self.od2)
        self.root.bind('u', self.od2.pause_off)
        self.root.bind('p', self.od2.pause_on)        
        self.root.bind('q', self.od2.stop) 
        
        # track,x,y,width,height,(pause at start = before,after,no),loaded callback
        self.od2.load('5sec.mp4','HDMI-2',100,100,100,100,'before',self.loaded2_callback)

    def loaded2_callback(self):
        self.vlc.log ('loaded 2')
        # (pause at end = yes,no), end callback
        self.od2.show('no',None,self.end2_callback)
        
    def end2_callback(self,status):
        self.vlc.log ('ended 2',status)



    def play3(self,event):
        # play first track normally
        self.vlc.log ('load 3')
        self.od3=VLCDriver(self.root)
        self.vlc_list.append(self.od3)
        self.root.bind('u', self.od3.pause_off)
        self.root.bind('p', self.od3.pause_on)        
        self.root.bind('q', self.od3.stop) 
        # track,x,y,width,height,(pause at start = before,after,no),loaded callback
        self.od3.load('5sec.mp4','HDMI-2',100,100,100,100,'before',self.loaded3_callback)

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
            #self.root.bind('u', self.od4.pause_off)
            #self.root.bind('p', self.od4.pause_on)        
            #self.root.bind('q', self.od4.stop) 
            self.od4.load('xthresh.mp4','HDMI-2',100,100,100,100,'before',self.loaded4_callback)
        else:
            #quit or nice_day, just return
            # get out of the callback
            self.vlc.log ('ending 3  other than pause at end',status)
            self.root.after(1,self.finished)

    def loaded4_callback(self):
        self.vlc.log ('loaded 4')
        self.vlc.log ('start showing 4')        
        self.od4.show('no',self.od3,self.end4_callback)
        #self.od3.pause_off()
        #self.od3.stop('')

        
    def end4_callback(self,status):
        self.vlc.log ('end show 4',status)
        self.root.after(1,self.finished)
        
    def finished(self):
        self.vlc.log ('finished')
        return
    
    
if __name__ == '__main__':    
    pp=PiPresents()
 

