

def main(this_file):
	
	
	import csv
	import matplotlib.pyplot as p
	from collections import defaultdict
	from datetime import datetime

	# import constants for the days of the week
	from matplotlib.dates import MO, TU, WE, TH, FR, SA, SU
	from matplotlib.dates import DayLocator, HourLocator, DateFormatter, drange
	from numpy import arange


	a = defaultdict(list) # each value in each column is appended to a list

	with open(this_file) as f:
		fieldnames = ['date', 'Tues','Wed','Thu','Fri','Sat mat','Sat','Total']
		reader = csv.DictReader(f, fieldnames) # read rows
				
		for row in reader: # read a row as {column1: value1, column2: value2,...}
			for (k,v) in row.items(): # go over each column name and value
				if k=="date":
					a[k].append(datetime.strptime(v,"%Y-%m-%dT%H:%M"))
				else:
					a[k].append(v) # append the value into the appropriate list based on column name k
        
	#print a
	
	fig,ax = p.subplots()
	ax.plot_date(a['date'],a['Total'],'.-')
	ax.xaxis.set_major_locator(DayLocator())
	#ax.xaxis.set_minor_locator(HourLocator(arange(0, 25, 6)))
	ax.xaxis.set_major_formatter(DateFormatter('%a %Y-%m-%d'))
	ax.grid()
	ax.fmt_xdata = DateFormatter('%a %Y-%m-%d %H:%M:%S')
	fig.autofmt_xdate()
	
	p.show()


#main('dagenham_test.log')
#main('dagenham.log')
main('eastwick.log')
