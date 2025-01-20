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
import math
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


def saveFile(file, data, mode="w"):
    print("file:", file)
    try:
        with open(file, mode) as f:
            f.write(data)
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
def init(system:dict,settings:dict,network:Network) -> bool:
    while True:
        if network.start():
            print("Connected to {}".format(network.provider))
            system["network"] = networkCheck()
            system["location"] = getLocation()
            return True
        else:
            print("Failed to connect to {}".format(network.provider))
            time.sleep(60)
    

def track(network, routes ,interval) -> str:
    connection = network.connect()
    data = getLocation()
    requestAmount = 200

    response, headers=network.post(
        path=		routes["location"],
        data= 		data,
        headers=	{"Connection":"close" },
        quantity=	requestAmount,
        interval=	interval,
        socket=		connection
    )
    print("Server Response:{} \n\n Sending nextLocation".format(response))
    connection.close()
    return response


class Update:
    def __init__(self,update):
        import ubinascii
        self.check = ubinascii
        self.version=  		update["version"]
        self.progress= 		update["progress"]
        self.fileName=  	update["fileName"] 
        self.fileSize=  	update["fileSize"]
        self.amountWritten= update["amountWritten"]
        self.chunkSize= 	update["chunkSize"]
        self.chunk =		""
        self.checkSum= 		update["checkSum"]

    def toDict(self):
        return {
            "version":self.version,
            "progress":self.progress,
            "fileName":self.fileName,
            "fileSize":self.fileSize,
            "amountWritten":self.amountWritten,
            "chunkSize":self.chunkSize,
            "checkSum":self.checkSum
        }
    

    def progressFile(self):
        progress = self.amountWritten/self.fileSize
        percentage = math.floor(progress*100)
        self.progress = percentage


    def	runCheckSum(self):
            checkSum = self.check.crc32(self.chunk)
            self.checkSum = str(checkSum) 
            return self.checkSum 
        
        
        
        
        
    


def processChunk(data: Update, network: Network, routes: dict) -> str:
    response,_= network.post(
        path=routes["update"],
        data=data.toDict(),
        headers={"Connection": "close"},
        quantity=1,
    )
    # if the file has been written return next instruction from server
    if data.fileSize <= data.amountWritten and data.amountWritten !=0:
        print("File has been written:",response)
        nextInstruction = ujson.loads(response)
        nextInstruction["data"] = ujson.loads(nextInstruction["data"])
        return nextInstruction
    
    
    # if the file has not been written, write the next chunk
    data.chunk= response
    data.runCheckSum()

    saveFile(BASEPATH+data.fileName, response, "a")
    data.amountWritten += len(response)
    data.progressFile()
    print("Amount Written:{} for File:{} \n The Check sum for the file{}".format(data.amountWritten, data.fileName,data.checkSum))
    nextInstruction = {"action":"update","data":data.toDict()}
    print("\n\n NEXT SET OF INSTRUCTIONS: ",nextInstruction)
    return nextInstruction



def parseInstruction(instruction:dict,network:Network,routes:dict)->str:
    print("Recieved Instructions from Server: {}".format(instruction))
    MODE = None 
    currentAction = instruction["action"]
    instruction["chunkSize"] = network.bufferSize

    if currentAction  == "update":
        update = Update(instruction["data"])
        update.chunkSize = network.bufferSize
        nextInstruction=processChunk(update,network,routes)
        return parseInstruction(nextInstruction,network,routes)
    elif currentAction == "updateState":
        pass
    elif currentAction == "Fault":
        pass
    elif currentAction == "Idle":
        pass
    elif currentAction == "reboot":
        pass
    elif currentAction == "print":
        print("INSTRUCTION Print from server:{}".format(instruction["data"]))
        pass
    else:
        pass
    return MODE





def updateSystem(network, routes):
    update = {}
    update["version"] = "0.0.1"
    update["progress"] = 0
    update["fileName"] = ""
    update["fileSize"] = 0
    update["amountWritten"] = 0
    update["chunkSize"] = 1046
    update["checkSum"] = "0.0.1"

    connection = network.connect()
    network.bufferSize = update["chunkSize"]
    data = update
    requestAmount = 1

    if update["progress"] == 0:
        instruction,header =network.post(
            path=		routes["update"],
            data= 		data,
            headers=	{"Connection":"close" },
            quantity=	requestAmount,
            interval=	0,
            socket=		connection
        )
        print(instruction)
        instruction = ujson.loads(instruction)
        instruction["data"] = ujson.loads(instruction["data"])
        parseInstruction(instruction,network,routes)
        connection.close()
        return






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
    currentMode = modes["currentMode"] 
    if currentMode== "tracking":
        print("Starting Tracking")
        track(
            network =   network, 
            routes  =   settings["server"]["routes"],
            interval=   modes[currentMode]["interval"]
        )
    elif currentMode == "idle":
        print("Entering Idle Mode")
        pass
    elif currentMode == "update":
        print("Entering Update Mode")
        updateSystem(
            network,
            settings["server"]["routes"]
            )
    elif currentMode == "printing":
        print("Joe mama")

    saveJson(BASEPATH+"System/iving.json", data)
    shutdown()


if __name__ == "__main__":
    main()

