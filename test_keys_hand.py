# import necessary packages
import cv2
import numpy as np
import mediapipe as mp
import tensorflow as tf
from keras.models import load_model
from time import sleep
from statistics import mode
import matplotlib.pyplot as plt


# initialize mediapipe
mpHands = mp.solutions.hands
hands = mpHands.Hands(max_num_hands=1, min_detection_confidence=0.7)
mpDraw = mp.solutions.drawing_utils

# Initialize the webcam
cap = cv2.VideoCapture(0)

rectangles = []
keys = []
#initialize rectangles

while(1):
    _, frame = cap.read()
    #frame = cv2.imread('C:\\Users\\cshu\\Documents\\shool_work\\2023-2024\\sem1\\452\\project\\testHand\\keys.jpg')
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    #GLOBAL THRESH
    #_, thresh = cv2.threshold(gray, 70, 255, cv2.THRESH_BINARY_INV)
    
    # Contrast enhancement
    equ = cv2.equalizeHist(gray)
    #blur = cv2.GaussianBlur(equ,(5,5),0)
    blur = cv2.bilateralFilter(equ,9,75,75)

    #OTSU THRESH
    _, thresh = cv2.threshold(blur,0,255,cv2.THRESH_BINARY_INV+cv2.THRESH_OTSU)
    cv2.imshow("Binary", thresh)


    ##------------------finding the outer border largest rectangle----------
    #dilation to connect the black rectangles with the outer black rectangle
    kernel = np.ones((5,5),np.uint8)
    dilated = cv2.dilate(thresh, kernel, iterations = 2)

    cv2.imshow("Dialated", dilated)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    largest_rectangle = None
    largest_area = 0
    largest_approx = None

    for cnt in contours:
        # Approximate the contour to a polygon
        epsilon = 0.02 * cv2.arcLength(cnt, True)
        approx = cv2.approxPolyDP(cnt, epsilon, True)

        # Check if the polygon is a rectangle
        if len(approx) == 4:
            area = cv2.contourArea(cnt)

            #update the largest rectangle
            if area > largest_area:
                largest_rectangle = cnt
                largest_area = area
                largest_approx = approx

    # Draw the largest rectangle on the frame
    if largest_rectangle is not None:
        cv2.drawContours(frame, [largest_rectangle], -1, (0, 255, 0), 2)


        corners = largest_approx.reshape(-1, 2)
        print(corners)
        plt.imshow(thresh)

        # Sort corners based on the sum of x and y
        corners = sorted(corners, key=lambda corner: corner[0] + corner[1])

        # Assign corners based on the sum of x and y
        top_left, _ , _, bottom_right = corners

        # Assign the remaining corners based on y value
        if corners[1][1] < corners[2][1]:
            top_right, bottom_left = corners[1], corners[2]
        else:
            top_right, bottom_left = corners[2], corners[1]

        _, _, border_w, border_h = cv2.boundingRect(largest_rectangle)

        # Compute the perspective transform matrix
        src_pts = np.float32([top_left, top_right, bottom_right, bottom_left])
        dst_pts = np.float32([[0, 0], [border_w-1, 0], [border_w-1, border_h-1], [0, border_h-1]])
        M = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped = cv2.warpPerspective(thresh, M, (border_w, border_h))
        cv2.imshow("Warped", warped)
        warpCopy = warped

        #----------------Find solid black rectangles (black keys)---------------------
        inv_M = cv2.getPerspectiveTransform(dst_pts, src_pts)

        # Use morphological operations to remove the lines
        kernel = np.ones((7,7),np.uint8)
        thresh = cv2.morphologyEx(warped, cv2.MORPH_OPEN, kernel)

        contours, _ = cv2.findContours(thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        #filter contours based on area
        contours = [cnt for cnt in contours if (cv2.contourArea(cnt) > 500 and cv2.contourArea(cnt) < 10000)]
        contours.sort(key=cv2.contourArea, reverse=True)

        areas = [cv2.contourArea(cnt) for cnt in contours]
        most_common_area = 0
        if(areas):
            most_common_area = mode(areas)

        #filter contours based on most common area (should be just the black keys remaining)
        contours = [cnt for cnt in contours if 0.7 * most_common_area <= cv2.contourArea(cnt) <= 1.3 * most_common_area]

        keys = []
        black_keys = [] #these are warped
        for cnt in contours:
            # Approximate the contour to a polygon
            epsilon = 0.02 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)

            #keys.append(approx)
            #approximately a rectangle
            if len(approx) == 4:
                # Get the bounding rectangle of the contour
                x, y, w, h = cv2.boundingRect(cnt)
                cv2.rectangle(warpCopy, (x, y), (x + w, y + h), (255, 0, 0), 2)
                rect = np.array([[x, y], [x+w, y], [x+w, y+h], [x, y+h]], dtype="float32")
                #inv_M = cv2.getPerspectiveTransform(dst_pts, src_pts) define this above
                inv_rect = cv2.perspectiveTransform(rect.reshape(-1,1,2), inv_M)
                inv_rect = inv_rect.astype(int)

                keys.append(inv_rect)
                black_keys.append([x,y,w,h])

                # Draw the rectangle on the original frame
                cv2.polylines(frame, [inv_rect], True, (255, 0, 0), 2)

                # Check the aspect ratio of the bounding rectangle
                aspect_ratio = float(w)/h
                #if 0.6 <= aspect_ratio <= 0.15:
                #    # Store the polygon as a key
                #    keys.append(approx)
                #
                #    #cv2.drawContours(frame, [approx], -1, (255, 0, 0), 2)
                #    cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 0, 0), 2)

            
        cv2.imshow("Warp copy", warpCopy)

        
        ##-----------------find white keys-----------------
        num_polygons = 14 #CHANGE THIS VAL LATER, INFER FROM NUM OF BLACK KEYS
        polygons = []
        #split border into polygons (white keys)
        for i in range(num_polygons):
            x1 = i * border_w // num_polygons
            x2 = (i + 1) * border_w // num_polygons
            polygon = np.array([[x1, 0], [x2, 0], [x2, border_h-1], [x1, border_h-1]], dtype="int")
            polygons.append(polygon)

        #create mask to fill the smaller rectangles (black keys)
        mask = np.zeros_like(warpCopy)
        for curr_key in black_keys:
            # Get the bounding rectangle of the contour
            x, y, w, h = curr_key#cv2.boundingRect(cnt)
            # Fill the rectangle on the mask
            cv2.rectangle(mask, (x, y), (x + w, y + h), (255, 255, 255), -1)

        #subtract smaller rectangles from larger polygons (white - black)
        for polygon in polygons:
            poly_mask = np.zeros_like(warpCopy)
            cv2.fillPoly(poly_mask, [polygon], (255, 255, 255))
            poly_mask = cv2.subtract(poly_mask, mask)

            # Find contours in the polygon mask
            poly_contours, _ = cv2.findContours(poly_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Approximate the contours to polygons and add them to keys
            for cnt in poly_contours:
                epsilon = 0.01 * cv2.arcLength(cnt, True)
                approx = cv2.approxPolyDP(cnt, epsilon, True)

                transformed_approx = cv2.perspectiveTransform(approx.reshape(-1,1,2).astype('float32'), inv_M)
                # Reshape back to original shape and convert to int
                transformed_approx = transformed_approx.reshape(-1,1,2).astype(int)

                keys.append(transformed_approx)
                cv2.drawContours(frame, [transformed_approx],  -1, (0, 0, 255), 2)
        

    cv2.imshow("Preview", frame)
    
    #input("Press any key to continue...")
    if cv2.waitKey(1) == ord('q'):
        break

    
# Calculate the x-coordinates of the centroids of the keys
x_centroids = [np.mean(key[:, 0, 0]).tolist() for key in keys]
# Create a list of tuples where each tuple is (x_centroid, key)
keys_with_x_centroids = list(zip(x_centroids, keys))
# Sort the list of tuples by the x-coordinate of the centroid
keys_with_x_centroids.sort()
# Update the keys list with the sorted keys
keys[:] = [key for x_centroid, key in keys_with_x_centroids]



while True:
    # Read each frame from the webcam
    #sleep(1)
    _, frame = cap.read()

    height, width, c = frame.shape

    # Flip the frame vertically
    #frame = cv2.flip(frame, 1)

    framergb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Get hand landmark prediction
    result = hands.process(framergb)

    # print(result)
    
    className = ''

    for key in keys:
        cv2.drawContours(frame, [key], -1, (0, 255, 0), 2)
        #xKey, yKey, wKey, hKey = key
        #cv2.rectangle(frame, (xKey, yKey), (xKey + wKey, yKey + hKey), (0, 255, 0), 2)

    # post process the result
    if result.multi_hand_landmarks:
        landmarks = []
            
        for handslms in result.multi_hand_landmarks:
            for lm in handslms.landmark:
                # print(id, lm)
                lmx = int(lm.x * width)
                lmy = int(lm.y * height)

                landmarks.append([lmx, lmy])

            # Drawing landmarks on frames
            mpDraw.draw_landmarks(frame, handslms, mpHands.HAND_CONNECTIONS)

            index_finger_tip = handslms.landmark[mpHands.HandLandmark.INDEX_FINGER_TIP]
            index_finger_tip_x = int(index_finger_tip.x * width)
            index_finger_tip_y = int(index_finger_tip.y * height)
            # draw a box around the finger tip
            cv2.rectangle(frame, (index_finger_tip_x - 10, index_finger_tip_y - 10), (index_finger_tip_x + 10, index_finger_tip_y + 10), (0, 0, 225), 2)

            #print(f"Index Finger Tip Position: ({index_finger_tip_x}, {index_finger_tip_y})")
            for i, key in enumerate(keys):
                # Use cv2.pointPolygonTest to check if the index finger tip is inside the key
                inside = cv2.pointPolygonTest(key, (index_finger_tip_x, index_finger_tip_y), False) >= 0

            #for i, (xKey, yKey, wKey, hKey) in enumerate(keys):
                #inside = xKey <= index_finger_tip_x <= xKey + wKey and yKey <= index_finger_tip_y <= yKey + hKey
                #print(f"Checking Key {i} at {xKey}, {yKey}, {wKey}, {hKey}")
                if inside:
                    print(f"INSIDE Key {i}")
                    

    # Show the final output
    cv2.imshow("Output", frame) 

    if cv2.waitKey(1) == ord('q'):
        break

# release the webcam and destroy all active windows
cap.release()

cv2.destroyAllWindows()
