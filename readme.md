Experiments into replacing omxplayer with VLC in Pi Presents.

omxplayer is deprecated because the underlying OMX display layer is also deprecated. The Raspberry Pi Foundation has suggested replacing it with VLC.

Recently the PI version of VLC has been extended to provide additional display features which are useable in the --vout mmal-vout display option; this display option displays videos as overlays in a designated display layer without borders in a manner similar to omxplayer.

The recent extensions have added windowing, cropping and making the background transparent. The last of these has potentially limited use as transparency reveals an empty vlc related X Window which steals the cursor and cannot be moved or removed. The extensions can be found at https://github.com/RPi-Distro/vlc/issues/12 and https://github.com/RPi-Distro/vlc/issues/13. Details of crop and aspect-ratio https://github.com/RPi-Distro/vlc/issues/17

For Pi Presents I need the following special facilities:

a. Windowing (--win in omxplayer terms ) aspect ratio bending and cropping.

b.The ability to pause a video just before the first frame, just after the first frame, and very near the end of the video. These allow the near gapless operation of mediashows.

c. A transparent background to the X layer on which could be displayed images and text using Tkinter and PIL. Both of these require X Windows to be used.

I have written proofs of concept programs for four of the methods of controlling VLC to see if I could satisfy the above requirements.  

vlcdbus.py - control vlc using dbus. vlc is started as a seperate sub-process and controlled by its dbus interface. I had a small problem with the reading duration . Pausing the video worked well as vlc provides position to greater than frame accuracy but it failed on the transparency because of the legacy VLC related X Window described above. The only way to remove this window was to remove the display from VLC (DISPLAY= ) but this disabled dbus. If you don't want transparency or user interaction then this method works well.

vlcpy.py - control VLC using the python-vlc library.  VLC and the test harness become the same process. The performance was the same as the dbus interface including the legacy X Window. The DISPLAY= method of removing the window does not work because both VLC and the test harness are the same program so any images or text produced by PIL/Tkinter are not displayed.If you don't want transparency or user interaction then this works well.

vlcrc.py - control VLC using its -rc interface module. VLC is started as a seperate sub-process and controlled by its text based -rc interface. python-pexpect is used as a sophicated pipe between them. Transparency works well because DISPLAY= suppresses VLC's x related display without affecting any of its functionality. The one drawback I found was pausing near the end of the track as postion is reported only to 1 second intervals and the GET-TIME command blocks for 50mS; not good in a cooperative scheduled system. I fudged a position reporting system using clock time but this is unlikely to produce as accurate results as omxplayer leading to the end of videos being lost.

vlcdrive.py and vlcplayer.py - BEST. This solution solves the timing problems with vlcrc.py and also removes the extraneous X-window. It uses python-libvlc to control cvlc in a small python program that provides a CLI interface. This can be run with DISPLAY= python3 vlcdriver.py as a sub-process from another python program vlcplayer.py (or from the terminal). The CLI interface is non-blocking. All the 'real time' stuff is in vlcdriver.py. I communicate with vlcdriver.py using pexpect but other methods are possible. 

Also, for fun:

vlctrio.py -  re-implementation of vlcrc.py using the Trio asynchronous I/O library. Trio is an alternative to python's asyncio, one I could actually understand. If it had been around 5 years ago I would probably have written Pi Presents using it.  It also has a library to integrate Trio with Tkinter obtained from ??????, re-factored and included in the code.

INSTALLATION AND USE
Download the repository into a directory and execute using python3, lots of details in the code. All the examples are similar but not exactly so. They have lots of rough edges, you may need to refer to the code. You may need to instal additional libraries

The commands are:

1,2,3 - play a show. some of the shows use the second display on Pi4.
q - quit a show
p,u - pause and unpause
escape - close the application
