# resize_image.py

#########################################################

# Author: Jordan Carver

#########################################################
import cv2
def resize_image(image):
	resized_image = cv2.resize(image, (1280, 720), interpolation=cv2.INTER_AREA)
	return resized_image
