# drawing_utils.py

#########################################################

# Author: Jordan Carver

#########################################################
import cv2
import numpy as np
def draw_detections(image, results, draw_labels=True):
    drawn_image = image.copy()
    if results is not None:
        for result in results:
            if result.boxes is not None:
                boxes = results.boxes.xyxy.cpu().numpy()
                classes = results.boxes.cls.cpu().numpy()
                names = results.names
                scores = results.boxes.conf.cpu().numpy()
            else:
                print("NO OBJECTS DETECTED BIC BOI")
            for box, cls, score in zip(boxes, classes, scores):
                x1, y1, x2, y2 = map(int, box)
                class_name = names[int(cls)]
                confidence = score
                color = (0, 255, 0)
                x1_down_scaled = int(0.333 * x1)
                y1_down_scaled = int(0.333 * y1)
                x2_down_scaled = int(0.333 * x2)
                y2_down_scaled = int(0.333 * y2)
                cv2.rectangle(drawn_image, (x1_down_scaled, y1_down_scaled), (x2_down_scaled, y2_down_scaled), color, 2)
                if draw_labels:
                    label = f'{class_name} {confidence:.2f}'
                    (text_width, text_height), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    cv2.rectangle(drawn_image, (x1_down_scaled, y1_down_scaled - text_height - 10), (x1_down_scaled + text_width, y1_down_scaled), color, -1)
                    cv2.putText(drawn_image, label, (x1_down_scaled, y1_down_scaled - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
                    return drawn_image
