# Ticket counter
# For monitoring ticket sales from the Horsham Capitol via their Spektrix driven website
# Copyright Bisxuit 2016
# v0.2 2016-12-07

import sys
import time
import tempfile
import datetime
import os

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
		#self.timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")
		self.tickets_sold = 0
		self.tickets_available = 0
		self.read_config()
		
		
	def read_config(self):
		# Get the list of events for this production from text file defined on the command line
		self.performances = []
		if os.path.isfile(self.config_file):
			for line in open(self.config_file):
				if len(line.strip())==0:
					continue
				elif line[0]=="#":
					self.title=line[1:].strip()
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
	
	
	def pprint(self):
		output_text = self.title
		output_text += "\n"+datetime.datetime.now().strftime("%Y-%m-%d %A %H:%M")
		for e in self.performances:
			output_text += "\n  "+e.desc+": "+str(e.tickets_sold) #(+x)
		output_text += "\n\nTotal sales: "+str(self.tickets_sold)
		return output_text
	
	
	def csv_print(self):
		output_text = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")
		for e in self.performances:
			output_text += ","+str(e.tickets_sold)
		output_text += ","+str(self.tickets_sold)
		return output_text
			
			
	def update(self):
		s = screenshot()
		#folder = "/home/tom/Code/Tickets/"
		folder = tempfile.gettempdir()
		self.timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H-%M")
		
		self.tickets_sold = 0
		self.tickets_available = 0
		
		for e in self.performances:
			e.get_sales(s,folder,self.timestamp)
			# Add up each performance
			self.tickets_sold += e.tickets_sold
			self.tickets_available += e.tickets_available
		
				
	def write_log(self):
		with open(self.log_file,'a') as fid:
			fid.write(self.csv_print()+'\n')
	
		
	def read_log(self):
		with open(self.log_file,'rt') as fid:
			return fid.readlines()
		
				
			
# Performance class for a single event on the Spektrix system (e.g. "Wednesday night of Dream")
class performance:
	def __init__(self,event_id,description):
		self.id = event_id
		self.desc = description
		self.url = "https://system.spektrix.com/capitolhorsham/website/ChooseSeats.aspx?EventInstanceId="+self.id
		self.tickets_available = 0
		self.tickets_sold = 0

	
	def get_sales(self,s,folder,timestamp):
		# Get a screenshot of the webpage
		filename = folder+timestamp+"_"+self.desc+"_"+self.id+".png"
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
			# Keep the picture for later analysis (could be sold out, or event passed)
			# TODO - check timestamp against event time from Spektrix
			print "Unexpected number of seats: "+seats_total+ " for: "+self.desc+" "+timestamp
		else:
			pass
			#i.delete()
			
		# However, not all seats are available for sale (and this is not entirely predictably)
		# Front three rows out (pit used) = 47
		# Sound desk in auditorium (musicals) = 12
		# Other seats reserved = 15 (but may be opened at some point)
		# These numbers should be calibrated against the official printouts from the Capitol
		# This will also tell you how many complimentary tickets are included.		
		
		# Comment out appropriate lines here
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



def main(config_file,command):
	if command == "update":
		p = production(config_file)
		p.update()
		print p.pprint()
		p.write_log()
	elif command == "help":
		print "Usage is: python capitol_ticket_counter.py <config_file> [<action>]"
		print "Actions are: update, help, email, setup"
	elif command == "email":
		# TODO - check log for changes and email an update
		pass
	elif command == "setup":
		# TODO - wizard for choosing events
		pass
	else:
		print "Command line option not recognised: "+command
		
		
		
# Logic to sort out command line options
if __name__ == '__main__':
	if len(sys.argv)>2:
		main(sys.argv[1],sys.argv[2])
	elif len(sys.argv)>1:
		main(sys.argv[1],'update')
	else:
		main('dagenham.conf','update')
