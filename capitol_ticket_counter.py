# Ticket counter
# For monitoring ticket sales from the Horsham Capitol via their Spektrix driven website
# Copyright Bisxuit 2016
# v0.2 2016-12-07

import sys
import time
import tempfile
from datetime import datetime
import os
from copy import deepcopy
import subprocess

# For pixel counting
from PIL import Image

# For screenshots of web pages
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4.QtWebKit import *



# Production class for a set of performances (e.g. "A Midsummer Night's Dream")
class production():
	def __init__(self,config_file):
		self.config_file = config_file
		self.log_file = config_file.replace(".conf",".log")
		self.tickets_sold = 0
		self.tickets_available = 0
		self.email = ''
		self.read_config()
		self.change = 0
		self.time_change = 0
		
	def read_config(self):
		# Get the list of events for this production from text file defined on the command line
		self.performances = []
		if os.path.isfile(self.config_file):
			for line in open(self.config_file):
				if len(line.strip())==0:
					continue
				elif line[0]=="#":
					self.title=line[1:].strip()
				elif line[0]=="@":
					self.email = line[1:].strip()
				else:
					try:
						temp_desc = line.split(",")[0].strip()
						temp_id = line.split(",")[1].strip()
			
					except:
						print "Bad line in "+self.config_file+": "
						print "   "+line
						continue
						
					self.performances.append(performance(temp_id,temp_desc))
		else:
			print "Config file not found: "+self.config_file
			sys.exit()
	
	
	def pprint(self,show_changes = True):
		output_text = self.title
		if self.time_change<>0 and show_changes:
			output_text += "\n"+datetime.strftime(self.timestamp,"%Y-%m-%d %A %H:%M") + "  (in last "+str(self.time_change)+")"
		else:
			output_text += "\n"+datetime.strftime(self.timestamp,"%Y-%m-%d %A %H:%M") # Slightly more human readable than ISO8601
		
		for e in self.performances:
			if e.change<>0 and show_changes:
				output_text += "\n  "+e.desc+": "+str(e.tickets_sold) +"  ("+"%+d"%e.change+")"
			else:
				output_text += "\n  "+e.desc+": "+str(e.tickets_sold)
				
		if self.change<>0 and show_changes:
			output_text += "\n\nTotal sales: "+str(self.tickets_sold)+"  ("+"%+d"%self.change+")"
		else:
			output_text += "\n\nTotal sales: "+str(self.tickets_sold)
		return output_text
	
					
	def write_log(self):
		output_text = datetime.strftime(self.timestamp,"%Y-%m-%dT%H:%M") # ISO8601
		for e in self.performances:
			output_text += ","+str(e.tickets_sold)
		output_text += ","+str(self.tickets_sold)
		
		with open(self.log_file,'a') as fid:
			fid.write(output_text+'\n')

						
	def update(self):
		s = screenshot()
		folder = tempfile.gettempdir()+"/"
		self.timestamp = datetime.now()
		
		self.tickets_sold = 0
		self.tickets_available = 0
		some_failed = False
		
		for e in self.performances:
			if e.get_sales(s,folder):
				# Add up each performance
				self.tickets_sold += e.tickets_sold
				self.tickets_available += e.tickets_available
				
			else:
				# Failed
				some_failed = True
				
		if some_failed:
			return 0
		else:
			return 1
		
		
	def read_last_log(self):
		with open(self.log_file,'rt') as fid:
			# Read last two lines from file
			temp = tail(fid,2)
		
		if len(temp)<2:
			print "Not enough data"
			return 0
			
		then = temp[0].split(',')
		now = temp[1].split(',')
		
		self.timestamp = datetime.strptime(now[0],"%Y-%m-%dT%H:%M")
		self.time_change = self.timestamp - datetime.strptime(then[0],"%Y-%m-%dT%H:%M")
		i = 1
		for e in self.performances:
			e.tickets_sold = int(now[i])
			e.change = int(now[i])-int(then[i])
			i+=1

		self.tickets_sold = int(now[i])
		self.change = int(now[i])-int(then[i])
		if self.change==0:
			return 0
		else:
			return 1
	
	
	def send_email(self,email="",show_changes = True):
		if email<>"":
			if show_changes:
				subject = 'Ticket sales: %d  (%+d)' % (self.tickets_sold,self.change)
			else:
				subject = 'Ticket sales: %d'%self.tickets_sold
			process = subprocess.Popen(['mail', '-s', subject,email],stdin=subprocess.PIPE)
			process.communicate(self.pprint(show_changes))
		else:
			print self.pprint(show_changes)
		
		
			
# Performance class for a single event on the Spektrix system (e.g. "Wednesday night of Dream")
class performance:
	def __init__(self,event_id,description):
		self.id = event_id
		self.desc = description
		self.url = "https://system.spektrix.com/capitolhorsham/website/ChooseSeats.aspx?EventInstanceId="+self.id
		self.tickets_available = 0
		self.tickets_sold = 0
		self.change = 0

	
	def get_sales(self,s,folder):
		# Get a screenshot of the webpage (to temp file, so not bothered about overwriting/readability)
		filename = folder+self.id+".png"
		# This can poo to stdout
		s.capture(self.url,filename)
		
		# Crop all the extra crap out
		i = Image.open(filename)
		i = i.crop((160,420,800,960))
		i.save(filename)
		
		# Count sold seats
		pixels_circle_unsold = 0
		pixels_circle = 0
		pixels_stalls_unsold = 0
		pixels_stalls = 0
				
		divider = 200 #pixels
		
		# Count the circle, 200 pixels down from the top
		for x in range(i.size[0]):
			for y in range(0,divider):
				p = i.getpixel((x,y)) #RGB
		
				# Total non white pixels
				if p[0]<>255 and p[1]<>255 and p[2]<>255:
					pixels_circle+=1
			
				# Only unsold seats (and the balcony divider) have any colour
				if abs(p[0]-p[2])>0:
					pixels_circle_unsold+=1
		
		# Count the stalls, everything after 200 pixels from the top
		for x in range(i.size[0]):
			for y in range(divider+1,i.size[1]):
				p = i.getpixel((x,y)) #RGB
		
				# Total non white pixels
				if p[0]<>255 and p[1]<>255 and p[2]<>255:
					pixels_stalls+=1
			
				# Only unsold seats (and the balcony divider) have any colour
				if abs(p[0]-p[2])>0:
					pixels_stalls_unsold+=1
		
		i.close()

		 
		# Now remove various elements from picture that aren't seats
		# See https://system.spektrix.com/capitolhorsham/files/Theatre__8f80dc6e71e744afa0e17b9dbde8c2dd.gif
		
		# Remove purple divider between circle and stalls (only background bit with colour)
		pixels_circle_unsold += -1483
		pixels_stalls_unsold += -327
		
		# Remove divider, writing and other crap (black and grey)
		pixels_circle += -715
		pixels_stalls += -3191
		
		# Convert pixels to seats (109 pixels per blob)
		# Should result in integers, but round anyway
		seats_circle = int(round(pixels_circle/109.0))
		seats_circle_unsold = int(round(pixels_circle_unsold/109.0))
		seats_stalls = int(round(pixels_stalls/109.0))
		seats_stalls_unsold = int(round(pixels_stalls_unsold/109.0))
		
		seats_total = seats_circle + seats_stalls
		
		# Capitol theatre capacity:
		# Stalls (max)  = 309
		# Circle (max)  = 112
		# Theatre (max) = 421
		if seats_total<>421:
			print "Unexpected number of seats: "+str(seats_total)+ " for: "+self.desc
			return 0
					
		# However, not all seats are available for sale (and this is not entirely predictably)
		# Front three rows out (pit used) = 47
		# Sound desk in auditorium (musicals) = 12
		# Other seats reserved = 15 (but may be opened at some point)
		# These numbers should be calibrated against the official printouts from the Capitol
		# This will also tell you how many complimentary tickets are included.		
		
		# Comment out appropriate lines here - TODO, put in config
		# For a musical
		unavailable_seats = 47+12+15
		
		# For a play
		#unavailable_seats = 15
		
		# Is the circle open?
		if seats_circle_unsold==0 and seats_stalls_unsold<>0:
			# Probably not
			unavailable_seats += 112
			self.tickets_available = seats_stalls_unsold
		else:
			self.tickets_available = seats_stalls_unsold + seats_circle_unsold
				
		self.tickets_sold = 421 - unavailable_seats - seats_stalls_unsold - seats_circle_unsold
		
		i.close()
		return 1
	
				

class screenshot(QWebView):
    def __init__(self):
		self.app = QApplication(sys.argv)
		QWebView.__init__(self)
		self._loaded = False
		self.loadFinished.connect(self._loadFinished)
		

    def capture(self, url, output_file):
		self.load(QUrl(url))
		self.wait_load()
		# Set to webpage size
		frame = self.page().mainFrame()
		self.page().setViewportSize(frame.contentsSize())
		# Render image
		image = QImage(self.page().viewportSize(), QImage.Format_ARGB32)
		painter = QPainter(image)
		frame.render(painter)
		painter.end()
		# Print 'saving', output_file
		image.save(output_file)


    def wait_load(self, delay=0):
        # Process app events until page loaded
        while not self._loaded:
            self.app.processEvents()
            time.sleep(delay)
        self._loaded = False


    def _loadFinished(self, result):
        self._loaded = True



# Helper function
def tail(f, window=20):
	# Returns the last `window` lines of file `f` as a list.
    if window == 0:
        return []
    BUFSIZ = 1024
    f.seek(0, 2)
    bytes = f.tell()
    size = window + 1
    block = -1
    data = []
    while size > 0 and bytes > 0:
        if bytes - BUFSIZ > 0:
            # Seek back one whole BUFSIZ
            f.seek(block * BUFSIZ, 2)
            # read BUFFER
            data.insert(0, f.read(BUFSIZ))
        else:
            # file too small, start from begining
            f.seek(0,0)
            # only read what was not read
            data.insert(0, f.read(bytes))
        linesFound = data[0].count('\n')
        size -= linesFound
        bytes -= BUFSIZ
        block -= 1
    return ''.join(data).splitlines()[-window:]



def main(config_file,email="",command ="update"):
	if command == "update":
		p = production(config_file)
		if p.update():
			p.write_log()
			main(config_file,email,"changes")
		else:
			# Failed
			pass
		
	elif command == "summary":
		# Output latest totals, but without changes since last update
		p = production(config_file)
		p.read_last_log()
		p.send_email(email,False)
				
	elif command == "changes":	
		# Output latest totals, but only if changes have happened since last update
		p = production(config_file)
		if p.read_last_log():
			p.send_email(email,True)
				
	elif command == "setup":
		# TODO - wizard for choosing events
		pass

	elif command == "help":
		print "Usage is: python capitol_ticket_counter.py <config_file> [<email_address>] [<action>]"
		print "Actions are:"
		print "  update      :  Check current ticket sales and update log"
		print "  summary     :  Send regular update email (e.g. daily)"
		print "  changes	 :  Send email if any changes between last two updates"
		print "  plot        :  Produce graph of ticket sales over time from log"
		print "  help        :  Print this text"

	
	else:
		print "Command line option not recognised: "+command
		
		
		
# Logic to sort out command line options
if __name__ == '__main__':
	if len(sys.argv)>3:
		main(sys.argv[1],sys.argv[2],sys.argv[3])
	elif len(sys.argv)>2:
		main(sys.argv[1],sys.argv[2])
	elif len(sys.argv)>1:
		main(sys.argv[1])
	else:
		main('dagenham.conf')
