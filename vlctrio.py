

import trio
import RPi.GPIO as gpio
from tkinter import *
import collections
import traceback
from outcome import Error
from vlctrio_driver import VLCDriver
from vlctrio_logger import Logger


# TKHost implements guest mode functions
# Copyright 2020 Richard J. Sheridan
# Licensed under the Apache License, Version 2.0 (the "License");

class TkHost:
    def __init__(self, root):
        self.root = root
        self._tk_func_name = root.register(self._tk_func)
        self._q = collections.deque()

    def _tk_func(self):
        self._q.popleft()()

    def run_sync_soon_threadsafe(self, func):
        """Use Tcl "after" command to schedule a function call

        Based on `tkinter source comments <https://github.com/python/cpython/blob/a5d6aba318ead9cc756ba750a70da41f5def3f8f/Modules/_tkinter.c#L1472-L1555>`_
        the issuance of the tcl call to after itself is thread-safe since it is sent
        to the `appropriate thread <https://github.com/python/cpython/blob/a5d6aba318ead9cc756ba750a70da41f5def3f8f/Modules/_tkinter.c#L814-L824>`_ on line 1522.
        Tkapp_ThreadSend effectively uses "after 0" while putting the command in the
        event queue so the `"after idle after 0" <https://wiki.tcl-lang.org/page/after#096aeab6629eae8b244ae2eb2000869fbe377fa988d192db5cf63defd3d8c061>`_ incantation
        is unnecessary here.

        Compare to `tkthread <https://github.com/serwy/tkthread/blob/1f612e1dd46e770bd0d0bb64d7ecb6a0f04875a3/tkthread/__init__.py#L163>`_
        where definitely thread unsafe `eval <https://github.com/python/cpython/blob/a5d6aba318ead9cc756ba750a70da41f5def3f8f/Modules/_tkinter.c#L1567-L1585>`_
        is used to send thread safe signals between tcl interpreters.
        """
        # self.root.after_idle(lambda:self.root.after(0, func)) # does a fairly intensive wrapping to each func
        self._q.append(func)
        self.root.call('after', 'idle', self._tk_func_name)

    def run_sync_soon_not_threadsafe(self, func):
        """Use Tcl "after" command to schedule a function call from the main thread

        If .call is called from the Tcl thread, the locking and sending are optimized away
        so it should be fast enough.

        The incantation `"after idle after 0" <https://wiki.tcl-lang.org/page/after#096aeab6629eae8b244ae2eb2000869fbe377fa988d192db5cf63defd3d8c061>`_ avoids blocking the normal event queue when
        faced with an unending stream of tasks, for example "while True: await trio.sleep(0)".
        """
        self._q.append(func)
        self.root.call('after', 'idle', 'after', 0, self._tk_func_name)
        # Not sure if this is actually an optimization because Tcl parses this eval string fresh each time.
        # However it's definitely thread unsafe because the string is fed directly into the Tcl interpreter
        # from the current Python thread
        # self.root.eval(f'after idle after 0 {self._tk_func_name}')

    def done_callback(self, outcome):
        """End the Tk app.
        """
        print(f"Outcome: {outcome}")
        if isinstance(outcome, Error):
            exc = outcome.error
            traceback.print_exception(type(exc), exc, exc.__traceback__)
        self.root.destroy()

    def mainloop(self):
        self.root.mainloop()



# set up the gui and its callback references here
class TkDisplay:
    def __init__(self, root):
        self.root = root
        
        self.root.wm_title("VLC-Trio")
        self.root.resizable(False,False)
        self.root.geometry("%dx%d%+d%+d"  % (300,200,400,400))

        self.root.protocol("WM_DELETE_WINDOW", self.escape_fn)
        self.root.bind("<Escape>",self.escape_fn)
        self.root.bind("<Key>", lambda event : self.key_callback(event))

        self.label_var = StringVar()
        label = Label(self.root, text='hello', fg='black',textvariable=self.label_var)
        label.pack()
        
        self.my_button = Button(self.root, text='My Button')
        self.my_button.pack()        

    #escape key and close button
    def set_escape_callback(self,callback):
        self.escape_callback=callback

    # just loose the event arg
    def escape_fn(self,event=None):
        self.escape_callback()

    # printing keys
    def set_key_callback(self,callback):
        self.key_callback=callback
        
    def set_button_callback(self, fn):
        self.my_button.configure(command=fn)
        



class PiPresents():

    async def gpio_task(self):
        gpio.setwarnings(True)        
        gpio.setmode(gpio.BOARD)
        # dummy to stop gpio complaining
        gpio.setup(11,gpio.IN)
        count=0
        # use a CancelScope to end this simple task
        with trio.CancelScope() as self.gpio_scope:
            while True:
                print("  gpio: sample inputs",count)
                count +=1
                #await send_channel.send(['event ',str(count)])
                await trio.sleep(5)
        gpio.cleanup()
        print("  gpio: exiting!")


    # start Pi Presents
    async def start(self,display):
        self.logger=Logger()
        self.logger.init()
        # display (*args) is second arg of start_guest_run()
        self.display=display
        self.shower_list=[]
        #set up the display callbacks
        # for close button and escape key 
        display.set_escape_callback(self.escape_event)
        display.set_key_callback(self.input_event)

        print("PP: started!")
        # start nursery for the showers, the gpio and wait
        async with trio.open_nursery() as self.nursery:
            print("PP: starting gpio...")
            self.nursery.start_soon(self.gpio_task)
            print("PP: waiting for children to finish...")
            #await trio.sleep_forever() #need if no regular tasks to start
            # !!! should there be a manager task to receive all the input events rather than doing it here

            
        # -- we exit the nursery block here --
        print("PP: all tasks ended!")
        return 'trio ended'

    # escape key pressed tidy up in an ordered manner
    def escape_event(self):
        print ('PP: escape pressed')
        # terminate the gpio
        self.gpio_scope.cancel()
        #then close the nursery and and any running shows - doe not allow explicit show or track tidy up
        self.nursery.cancel_scope.cancel()

    def input_event(self,event):
        key=event.char
        print ('key',key)
        self.display.label_var.set(key)
        if key == "1":
            self.nursery.start_soon(self.play1,self.display)

        elif key == "2":
            self.nursery.start_soon(self.play2,self.display)

        elif key == "3":
            self.nursery.start_soon(self.play3,self.display)
            
        elif key == "l":
            self.nursery.start_soon(self.loop_play3,self.display)
        else:
            #offer the key to all the shows
            for shower in self.shower_list:
                shower.input_event(key)

    async def play1(self,display):
        print ('play1')
        # track 1 only
        self.od1=VLCDriver(self.nursery)
        self.shower_list.append(self.od1)
        # track,x,y,width,height,(volume 0>1024), (pause at start = before,after,no)
        await self.od1.load('5sec.mp4','HDMI-1',100,400,100,100,256,'after')
        # (pause at end = yes,no), previous player
        await self.od1.show('yes',None)
        self.shower_list.remove(self.od1)
        print ('end 1',self.shower_list)


    async def play2(self,display):
        print ('play2')
        self.od2=VLCDriver(self.nursery)
        self.shower_list.append(self.od2)
        # track,x,y,width,height,(pause at start = before,after,no)
        await self.od2.load('5sec.mp4','HDMI-2',100,100,100,100,256,'no')
        # (pause at end = yes,no), end callback
        await self.od2.show('no',None)
        self.shower_list.remove(self.od2)


    async def play3(self,display):
        # play first track normally
        self.od3=VLCDriver(self.nursery)
        self.shower_list.append(self.od3)
        # track,x,y,width,height,(pause at start = before,after,no)
        await self.od3.load('5sec.mp4','HDMI-1',100,100,200,200,256,'no')
        status = await self.od3.show('yes',None)
        print ('track 3 ending',status)
        if status == 'pause_at_end':
            print ('pause at end so load 4')
            self.od4=VLCDriver(self.nursery)
            self.shower_list.append(self.od4)
            await self.od4.load('xthresh.mp4','HDMI-1',200,200,300,300,64,'before')
            # od4.show() finishes od3
            self.nursery.start_soon(self.finish3) #start a task to do this as needs parallel execution
            status = await self.od4.show('no',self.od3) 
            self.shower_list.remove(self.od4)

            print ('end track 4',status,self.shower_list)    
        else:
            #quit or nice_day, just return
            print ('ending 3  other than pause at end',status)
            self.shower_list.remove(self.od3)
            print ('end 3 no pause',self.shower_list)
            self.od4=VLCDriver(self.nursery)
            self.shower_list.append(self.od4)
            await self.od4.load('xthresh.mp4','HDMI-1',200,200,300,300,64,'no')
            status=await self.od4.show('no',None)
            self.shower_list.remove(self.od4)
            print ('end track 4',status,self.shower_list)        

    async def finish3(self):
        await self.od3.finish()
        self.shower_list.remove(self.od3)
        
        
    async def loop_play3(self,display):
        while True:
            await self.play3(display)
            
if __name__ == '__main__':
    
    root = Tk()
    host = TkHost(root)   # code that runs Tkinter on top of Trio (or vice versa?)
    display = TkDisplay(root)  # defines the widgets in the display and their callbacks
    pp=PiPresents() 
    # display is second (*arg) of start_guest_run()
    trio.lowlevel.start_guest_run(
        pp.start,
        display,
        run_sync_soon_threadsafe=host.run_sync_soon_threadsafe,
        run_sync_soon_not_threadsafe=host.run_sync_soon_not_threadsafe,
        done_callback=host.done_callback,
    )
    host.mainloop()
    
    
