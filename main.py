import cellular as cell
import sys
import gps
import time
import uos
import ujson
import uio
import socket
sys.path.append("/t/System")
sys.path.append("/lib/")
import Network
import machine
import urequests
BASEPATH = "/t/"
SETTINGSPATH =  BASEPATH+ "System/Settings.json"




def loadJson(file):
    try:
        with open(file, "r") as f:
            settings = ujson.load(f)
            return settings
    except OSError as e:
        print(e)
        return None


def saveJson(file, data):
    try:
        with open(file, "w") as f:
            ujson.dump(data, f)
    except OSError as e:
        print(e)
        return None







def getLocation():
    location = {}
    ##latitude , longitude = gps.get_location()
    currentLocation = {"latitude": 64.46382, "longitude": -44.5345}
    location = currentLocation
    return location


def networkCheck():
    network = {}
    network["scan"] = cell.scan()
    network["imei"]= cell.get_imei()
    network["iccid"] = cell.get_iccid()
    network["quaility"] = cell.get_signal_quality()
    network["registered"] = cell.is_network_registered()
    network["status"] = cell.get_network_status()
    network["roaming"] = cell.get_signal_quality()
    try:
        network["register"] = cell.register() 
    except RuntimeError as e:
        pass
    network["statuons"] = cell.stations()
    return network


def shutdown():
    cell.gprs(False)
    print("GoodBye")


        


"""
Biggest issue I found is periods of Network is not available: is SIM card inserted?
this never seems to Correct its self via software, will need to debugg more
all the booting dosent work and sometimes even shutting the device off and back on fails
the one consistant hindrenss with the A8G Board I have seen. 


Really thinking it could be something with the physical sim card its self,
but sometimes it fix its self via code??

possibilitly that maybe the cell towers strength varies significantlty (really doubt this)

--ideas:
    - Rigorous Testing and Loging, sigh...
    - Final Version can implment external source/board to power cycle A9G Board( or find some software alternative)
"""
def init(system:dict,settings:dict,network:Network) -> bool  :
    while True:
        if network.start(attempt= 0):
            print("Connected to {}".format(network.provider))
            system["network"] = networkCheck()
            system["location"] = getLocation()
            return True
        else:
            print("Failed to connect to {}".format(network.provider))
            time.sleep(60)
            shutdown()
    

def track(network, routes ,interval) -> str:
    connection = network.connect()
    data = getLocation()
    
    response=network.post(
        path=		routes["location"],
        data= 		data,
        auth=		"",
        quantity=	500,
        interval=	interval,
        socket=		connection
    )
    print("Server Response:{} \n\n Sending nextLocation".format(response))
    connection.close()
    return response


def main():
    print("Starting System",)
    data = {}
    settings = loadJson(SETTINGSPATH)
    network = Network.new(settings["provider"],settings["server"])

    initialized= init(data,settings,network)
    if not initialized:
        # add some logging and maybe Error Handling
        print("Failed to initialize")
        return

    modes = settings["modes"]
    curreentMode = modes["currentMode"] 
    if curreentMode== "tracking":
        print("Starting Tracking")
        track(
            network =   network, 
            routes  =   settings["server"]["routes"],
            interval=   modes["currentMode"]["interval"]
        )
    elif curreentMode == "idle":
        print("Entering Idle Mode")
        pass

    saveJson(BASEPATH+"System/iving.json", data)
    shutdown()




if __name__ == "__main__":
    main()
