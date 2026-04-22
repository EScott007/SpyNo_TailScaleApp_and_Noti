# add_data_to_file


###################################################################

# Author: Jordan Carver

###################################################################
import time
def add_data_to_file(filename, data):
	try:
		with open(filename, 'a') as file:
			file.write(str(data) + '\n')
		##print(f"Data '{data}' successfully added to {filename}")
	except IOError as e:
		print(f"Error writing to file: {e}")
