# Ticket counter
# For monitoring ticket sales from the Horsham Capitol via their Spektrix driven website
# Copyright Bisxuit 2017-08-18

# TODO - better error checking, especially crap network connections
# TODO - Cloudify into AWS

import sys
import time
import tempfile
from datetime import datetime
import os
from copy import deepcopy
import subprocess

# For pixel counting
from PIL import Image,ImageChops


# Production class for a set of performances (e.g. "A Midsummer Night's Dream")
class production():
	def __init__(self,config_file):
		self.config_file = config_file
		self.log_file = config_file.replace(".conf",".log")
		# TODO - error check here
		self.reference_image = Image.open(config_file.replace(".conf",".png"))
		self.tickets_sold = 0
		self.tickets_available = 0
		self.email = ''
		self.reference_time = 1
		self.change = 0
		self.time_change = 0
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
				elif line[0]=="@":
					self.email = line[1:].strip()
				elif line[0]=="+":
					# Force the end time to 2200 on the final day specified in the text file.
					# TODO - sanitise input (only used for plotting at the moment)
					self.reference_time = datetime.strptime(line[1:].strip()+" 22:00","%Y-%m-%d %H:%M")
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
		folder = tempfile.gettempdir()+"/"
		self.timestamp = datetime.now()
		
		self.tickets_sold = 0
		self.tickets_available = 0
		some_failed = False
		
		for e in self.performances:
			if e.get_sales(folder,self.reference_image):
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
		if email=="" and self.email<>"":
			email = self.email
			
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

	
	def get_sales(self,folder,reference_image):
		# Get a screenshot of the webpage (to temp file, so not bothered about overwriting/readability)
		filename = folder+datetime.strftime(datetime.now(),"%Y-%m-%d_%H:%M")+"_"+self.id+".png"
		# This can poo to stdout
		screenshot(self.url,filename)
		
		# Crop all the extra crap out
		i = Image.open(filename)
		i = i.crop((90,400,900,1060))
		
		# Remove various elements from picture that aren't seats using reference image
		i = ImageChops.add(ImageChops.invert(reference_image), i)
		
		i.save(filename)

		
		# Count sold seats
		pixels_circle_unsold = 0
		pixels_circle = 0
		pixels_stalls_unsold = 0
		pixels_stalls = 0
				
		# These bits may need recalibrating for website/theatre changes
		divider = 280 #pixels
		pixels_per_seat = 170.0
		
		# Count the circle, 280 pixels down from the top
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
	
		# Convert pixels to seats (170 pixels per blob)
		# Should result in integers, but round anyway
		seats_circle = int(round(pixels_circle/pixels_per_seat))
		seats_circle_unsold = int(round(pixels_circle_unsold/pixels_per_seat))
		seats_stalls = int(round(pixels_stalls/pixels_per_seat))
		seats_stalls_unsold = int(round(pixels_stalls_unsold/pixels_per_seat))
		
		seats_total = seats_circle + seats_stalls
		
		# Capitol theatre capacity:
		# Stalls (max)  = 309
		# Circle (max)  = 112
		# Theatre (max) = 421
		if seats_total<>421:
			print "Unexpected number of seats: "+str(seats_total)+ " for: "+self.desc
			seats_total = float('nan')
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
			unavailable_seats += 5 #reserved in the circle
			self.tickets_available = seats_stalls_unsold + seats_circle_unsold
				
		self.tickets_sold = 421 - unavailable_seats - seats_stalls_unsold - seats_circle_unsold
		
		i.close()
		return 1
	
	
def screenshot(url, output_file):
	# Call Linux function from command line to get screenshot of webpage
	FNULL = open(os.devnull, 'w')
	process = subprocess.Popen(["wkhtmltoimage",url,output_file],stdin=subprocess.PIPE,stdout=FNULL,stderr=subprocess.STDOUT)
	process.wait()


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
	# Various different options here. 
	
	if command == "update":
		# Default is to run a full update and email changes if an email address is in the config file or on the command line.
		# This is the best option for running updates (e.g. called from cron every fifteen minutes)
		p = production(config_file)
		if p.update():
			p.write_log()
			main(config_file,email,"changes")
		else:
			# Failed
			pass
		
	elif command == "summary":
		# Output latest totals, but without including changes since last update (e.g. for a weekly update)
		p = production(config_file)
		p.read_last_log()
		p.send_email(email,False)
				
	elif command == "changes":
		# Output latest totals, but only if changes have happened since last update
		# This will go as an email if address is included in the config file or command line
		p = production(config_file)
		if p.read_last_log():
			p.send_email(email,True)
				
	elif command == "setup":
		# TODO - wizard for choosing events, reference image and output email address
		pass

	elif command == "plot":
		# Create a graph of ticket sales
		p = production(config_file)
		# TODO
		# TODO - compare to previous shows for which data exists

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
