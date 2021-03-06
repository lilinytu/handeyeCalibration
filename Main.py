import indydcp_client as indycli
import pyrealsense2 as rs
import cv2
import cv2.aruco as aruco

import numpy as np 
import sys 
from time import sleep
import math
import os
import datetime

import Config
from UtilSet import *
from HandEyeCalib import *

# opencv parameters
OpencvCriteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)          # termination criteria (maybe not used..)

'''
#####################################################################################
Robot Control/Status Functions
#####################################################################################
'''
def indyConnect(servIP, connName):
    # Connect
    obj = indycli.IndyDCPClient(servIP, connName)
    conResult = obj.connect()
    if conResult == False:
        print("Connection Failed")
        obj = None
    return obj

def initializeIndy7(indy):
    indy.reset_robot()
    status = indy.get_robot_status()
    print("Resetting robot")
    print("is in resetting? ", status['resetting'])
    print("is robot ready? ", status['ready'])
    if( status['direct_teaching'] == True):
        indy.direct_teaching(False)
    if( status['emergency'] == True):
        indy.stop_emergency()
    sleep(5)
    status = indy.get_robot_status()
    print("Reset robot done")
    print("is in resetting? ", status['resetting'])
    print("is robot ready? ", status['ready'])

def indyPrintJointPosition():
    print('### Test: GetJointPos() ###')
    joint_pos = indy.get_joint_pos()
    print ("Joint Pos: ")
    print (joint_pos)    

def indyPrintTaskPosition():
    task_pos = indy.get_task_pos()
    task_pos_mm = [task_pos[0], task_pos[1], task_pos[2],task_pos[3], task_pos[4], task_pos[5]]
    print ("Task Pos: ")
    print (task_pos_mm) 

def indyGetCurrentHMPose():
    task_pos = indy.get_task_pos()
    hm = HMUtil.convertXYZABCtoHMDeg(task_pos)
    return hm

def indyGetTaskPose():
    task_pos = indy.get_task_pos()
    return task_pos    

def indyMoveToTask(taskpos):
    indy.task_move_to(taskpos)


'''
#####################################################################################
Realsense Camera Control/Status Functions
#####################################################################################
'''
# initialize a realsense camera
def initializeRealsense():
    #Configure depth and color streams
    pipeline = rs.pipeline()
    config = rs.config()
    config.enable_stream(rs.stream.depth, Config.VideoFrameWidth, Config.VideoFrameHeight, rs.format.z16, Config.VideoFramePerSec)
    config.enable_stream(rs.stream.color, Config.VideoFrameWidth, Config.VideoFrameHeight, rs.format.bgr8, Config.VideoFramePerSec)

    # Start streaming
    pipeline.start(config)
    return pipeline

# covert realsense intrisic data to camera matrix
def convertIntrinsicsMat(intrinsics):
    mtx = np.array([[intrinsics.fx,             0, intrinsics.ppx],
                    [            0, intrinsics.fy, intrinsics.ppy],
                    [            0,             0,              1]])
    
    dist = np.array(intrinsics.coeffs[:4])
    return mtx, dist


'''
#####################################################################################
Utility Functions
#####################################################################################
'''
def drawText(img, text, imgpt):
    font = cv2.FONT_HERSHEY_PLAIN
    cv2.putText(img, text, imgpt, font, 1, (0,255,0),1,cv2.LINE_AA)


'''
#####################################################################################
Transform Matrix Functions
#####################################################################################
'''
# save a transform matrix to xml data as a file
def saveTransformMatrix(resultMatrix):
    calibFile = cv2.FileStorage("HandEyeCalibResult.xml", cv2.FILE_STORAGE_WRITE)
    calibFile.write("HEMatrix", resultMatrix)
    calibFile.release()

# get a transformation matrix which was created by calibration process
def loadTransformMatrix():
    calibFile = cv2.FileStorage("HandEyeCalibResult.xml", cv2.FILE_STORAGE_READ)
    hmnode = calibFile.getNode("HEMatrix")
    hmmtx = hmnode.mat()
    return hmmtx

'''
#####################################################################################
Mouse Event Handler
#####################################################################################
'''
global indy7Coord
def mouseEventCallback(event, x, y, flags, param):
    aligned_depth_frame = param
    if(event == cv2.EVENT_LBUTTONUP):
        print("-------------------------------------------------------")
        print("LBTNUP Event... " + str(x) + " , " + str(y))

    if(event == cv2.EVENT_MBUTTONUP):
        print("-------------------------------------------------------")
        print("MBTNUP Event... " + str(x) + " , " + str(y))

    if(event == cv2.EVENT_RBUTTONUP):
        print("-------------------------------------------------------")
        print("RBTNUP Event... " + str(x) + " , " + str(y))
        
        # get a camera-based coordinates for the current image pixel point
        depth = aligned_depth_frame.get_distance(int(x), int(y))
        depth_point = rs.rs2_deproject_pixel_to_point(depth_intrin, [int(x), int(y)], depth)

        # get a transformation matrix which was created by calibration process
        hmmtx = loadTransformMatrix()

        # print("Transform Matrix: ")
        # print(hmmtx)
        
        # print a camera based coordinates
        camCoord = np.array(((depth_point[0], depth_point[1], depth_point[2], 1)))
        text = "Camera Coord: %.5lf, %.5lf, %.5lf" % (depth_point[0], depth_point[1], depth_point[2])
        print(text)

        #indy7Coord = np.dot(hmmtx, camCoord)
        indy7Coord = np.dot(hmmtx, camCoord)

        print("Transfomred Robot-based Coordinate: ")
        print(indy7Coord)


'''
#####################################################################################
Key Event Handler
#####################################################################################
'''
def keyEventHandler(pressedKey, flagAruco, color_image, tvec, rvec, mtx, dist, handeye):

    goExit = False

    if pressedKey == ord('q'):
        goExit = True
    elif pressedKey == ord('d'):
        # set direct-teaching mode on
        print("direct teaching mode: On")
        indy.direct_teaching(True)
    elif pressedKey == ord('f'):
        # set direct-teaching mode off
        print("direct teaching mode: Off")
        indy.direct_teaching(False)
    elif pressedKey == ord('p'):
        indyPrintTaskPosition()

    if(flagAruco == False):
        print("Can't find any aruco marker.")
    else:
        if pressedKey == ord('c'):
            print("---------------------------------------------------------------")
            # get the current robot position
            currTaskPose = indyGetTaskPose()
            # capture additional matrices here
            handeye.captureHandEyeInputs(currTaskPose, rvec[0], tvec[0])
        elif pressedKey == ord('z'):
            handeye.resetHandEyeInputs()
        elif pressedKey == ord('m'):
            print("---------------------------------------------------------------")
            hmTransform = handeye.getHandEyeResultMatrixUsingOpenCV()
            print("Transform Matrix = ")
            print(hmTransform)
            saveTransformMatrix(hmTransform)
        elif pressedKey == ord('n'):
            print("---------------------------------------------------------------")
            # change a rotation vector to a rotation matrix
            rotMatrix = np.zeros(shape=(3,3))
            cv2.Rodrigues(rvec[0], rotMatrix)
            
            # transform a rotation matrix based on x-axis (for the purpose of test)
            # tansBase2TCP = np.array([[1.0, 0.0, 0.0],[0.0, -1.0, 0.0],[0.0, 0.0, -1.0]]) # 180 degree of x axis
            # rotMatrix = np.dot(tansBase2TCP, rotMatrix)

            # make a homogeneous matrix using a rotation matrix and a translation matrix as 
            hmCal2Cam = HMUtil.makeHM(rotMatrix, tvec[0])
            # print("Cal2Cam HM: ")
            # print(hmCal2Cam)
            xyzabc = HMUtil.convertHMtoXYZABCDeg(hmCal2Cam)
            #print(xyzabc)

            # get a transformation matrix which was created by calibration process
            hmmtx = loadTransformMatrix()

            # calcaluate the specific position based on hmInput
            hmWanted = HMUtil.makeHM(np.array([[1.0, 0.0, 0.0],[0.0, 1.0, 0.0],[0.0, 0.0, 1.0]]), np.array([0.0, 0.0, Config.HandEyeTargetZ]).T)
            hmInput = np.dot(hmCal2Cam, hmWanted)
            # print("hmInput: ")
            # print(hmInput)

            hmResult = np.dot(hmmtx, hmInput)
            # print("Result(hmInput): ")
            # print(hmResult)            

            # get a final homogeneous matrix for the current marker.
            #hmResult2 = np.dot(hmmtx, hmCal2Cam)
            # print("Result(hmCal2Cam): ")
            # print(hmResult2)

            # get a final xyzuvw for the last homogenous matrix
            xyzuvw = HMUtil.convertHMtoXYZABCDeg(hmResult)
            print("Final XYZABC: ")
            print(xyzuvw)

            # test move to the destination
            currPos = indyGetTaskPose()
            [xc,yc,zc,uc,vc,wc] = currPos

            [x,y,z,u,v,w] = xyzuvw

            # indy7 base position to gripper position
            xyzuvw = [x,y,z,u*(-1),v+180,w] 
            print(xyzuvw)
            indy.task_move_to(xyzuvw)

    return goExit

###############################################################################
# Hand-eye calibration process 
#   -                                                                
###############################################################################

if __name__ == '__main__':

    # connect to Indy
    indy = indyConnect(Config.INDY_SERVER_IP, Config.INDY_SERVER_NAME)
    if(indy == None):
        print("Can't connect the robot and exit this process..")
        sys.exit()

    # intialize the robot
    print("Intialize the robot...")
    initializeIndy7(indy)
    sleep(1)

    # ready to capture frames for realsense camera
    pipeline = initializeRealsense()

    # create an align object
    align = rs.align(rs.stream.color)

    # create a window to display video frames
    cv2.namedWindow('Capture Images')

    # create a variable for frame indexing
    flagFindMainAruco = False

    # use created camera matrix 
    if(Config.UseRealSenseInternalMatrix == False):
        calibFile = cv2.FileStorage("CameraCalibResult.xml", cv2.FILE_STORAGE_READ)
        cmnode = calibFile.getNode("cameraMatrix")
        mtx = cmnode.mat()
        dcnode = calibFile.getNode("distCoeff")
        dist = dcnode.mat()


    if(Config.UseNewCameraMatrix == True):
        newcameramtx, roi=cv2.getOptimalNewCameraMatrix(mtx,dist,(Config.VideoFrameWidth,Config.VideoFrameHeight),1,(Config.VideoFrameWidth,Config.VideoFrameHeight))

    # create a handeye calib. instance
    handeye = HandEyeCalibration()

    # get frames and process a key event
    try:
        while(True):
            # wait for a coherent pair of frames: depth and color
            frames = pipeline.wait_for_frames()

            # Align the depth frame to color frame
            aligned_frames = align.process(frames)

            # Get aligned frames
            aligned_depth_frame = aligned_frames.get_depth_frame() # aligned_depth_frame is a 640x480 depth image
            color_frame = aligned_frames.get_color_frame()
            if not aligned_depth_frame or not color_frame:
                continue

            # get internal intrinsics & extrinsics in D435
            depth_intrin = aligned_depth_frame.profile.as_video_stream_profile().intrinsics
            color_intrin = color_frame.profile.as_video_stream_profile().intrinsics
            #depth_to_color_extrin = aligned_depth_frame.profile.get_extrinsics_to(color_frame.profile)
            if(Config.UseRealSenseInternalMatrix == True):    
                mtx, dist = convertIntrinsicsMat(color_intrin)
            
            # Convert images to numpy arrays
            color_image = np.asanyarray(color_frame.get_data())
            depth_image = np.asanyarray(aligned_depth_frame.get_data())

            # operations on the frame
            gray = cv2.cvtColor(color_image, cv2.COLOR_BGR2GRAY)

            # set dictionary size depending on the aruco marker selected
            aruco_dict = aruco.Dictionary_get(aruco.DICT_5X5_250)

            # detector parameters can be set here (List of detection parameters[3])
            parameters = aruco.DetectorParameters_create()
            parameters.adaptiveThreshConstant = 7
            #parameters.cornerRefinementMethod = CORNER_REFINE_SUBPIX


            if(Config.UseNewCameraMatrix == True):
                dst = cv2.undistort(gray, mtx, dist, None, newcameramtx)
                corners, ids, rejectedImgPoints = aruco.detectMarkers(dst, aruco_dict, parameters=parameters)
            else:
                # lists of ids and the corners belonging to each id
                corners, ids, rejectedImgPoints = aruco.detectMarkers(gray, aruco_dict, parameters=parameters)

            # check if the ids list is not empty
            # if no check is added the code will crash
            if np.all(ids != None):
                # estimate pose of each marker and return the values
                # rvet and tvec-different from camera coefficients
                if(Config.UseNewCameraMatrix == True):
                    rvec, tvec ,_ = aruco.estimatePoseSingleMarkers(corners, Config.ArucoSize, newcameramtx, dist)
                else:
                    rvec, tvec ,_ = aruco.estimatePoseSingleMarkers(corners, Config.ArucoSize, mtx, dist)

                # TODO: consider how accurate the center point is as below.....
                # get the center of an Aruco Makers

                # should do something here using extracted aruco marker ids here
                flagFindMainAruco = False
                for idx in range(0, ids.size):
                    if(ids[idx] == Config.MainMarkerID) or (ids[idx] == Config.TestMarkerID):
                        if((rvec[idx].shape == (1,3)) or (rvec[idx].shape == (3,1))):
                            inputObjPts = np.float32([[0.0,0.0,0.0]]).reshape(-1,3)
                            imgpts, jac = cv2.projectPoints(inputObjPts, rvec[0], tvec[0], mtx, dist)
                            centerPoint = tuple(imgpts[0][0])
                            cv2.circle(color_image,centerPoint,1,(0,0,255), -1)                        

                            # print 3D position using realsense SDK
                            if(Config.UseHandEyePrint3DCoords == True):
                                depth = aligned_depth_frame.get_distance(centerPoint[0], centerPoint[1])
                                depth_point = rs.rs2_deproject_pixel_to_point(depth_intrin, [centerPoint[0], centerPoint[1]], depth)
                                print(str(depth_point) + str(' ') + str(tvec[0]))
                            
                            # find the main aruco marker 
                            flagFindMainAruco = True

                    if(Config.UseNewCameraMatrix == True):
                        aruco.drawAxis(color_image, newcameramtx, dist, rvec[idx], tvec[idx], 0.03)
                    else:
                        aruco.drawAxis(color_image, mtx, dist, rvec[idx], tvec[idx], 0.03)

                #(rvec-tvec).any() # get rid of that nasty numpy value array error

                # draw a square around the markers
                aruco.drawDetectedMarkers(color_image, corners)

                # code to show ids of the marker found
                # strg = ''
                # for i in range(0, ids.size):
                #     strg += str(ids[i][0])+', '

            else:
                # code to show 'No Ids' when no markers are found
                #cv2.putText(frame, "No Ids", (0,64), font, 1, (0,255,0),2,cv2.LINE_AA)
                flagFindMainAruco = False
                tvec = None
                rvec = None
                pass   
            
            # display the captured image
            cv2.imshow('Capture Images',color_image)
            # cv2.setMouseCallback('Capture Images', mouseEventCallback, aligned_depth_frame)
            
            # handle key inputs
            pressedKey = (cv2.waitKey(1) & 0xFF)
            if(pressedKey != 0xff):
                exitFlag = keyEventHandler(pressedKey, flagFindMainAruco, color_image, tvec, rvec, mtx, dist, handeye)
                if(exitFlag == True):
                    break

    finally:
        # direct teaching mode is disalbe before exit
        robotStatus = indy.get_robot_status()
        if( robotStatus['direct_teaching'] == True):
            indy.direct_teaching(False)
        # Stop streaming
        pipeline.stop()
    
    # arrange all to finitsh this application here
    cv2.destroyAllWindows()
    indy.disconnect()
        