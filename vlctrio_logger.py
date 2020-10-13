import time
import os
import sys

class Logger():
    log_file=None
    start_time=0
    
    def init(self):
        Logger.start_time=time.time()  # for logging
        self.work_dir=sys.path[0]
        Logger.log_file=open(self.work_dir+'/log.txt','a')
        print ('INIT LOGGER',self.work_dir)
        
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


    def terminate():
        Logger.log_file.close()
