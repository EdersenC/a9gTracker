import cellular
import socket
import ssl 
import ujson
import sys
import gc
import upip
import time
import machine



class new:
    def __init__(self,provider:str, settings):
        self.bufferSize = 130 # Blocks(or maybe socket timeout?) if greater than 130?
        self.provider 	= provider
        self.host 	  	= settings["host"]
        self.port 	  	= settings["port"]
        self.auth  	  	= settings["auth"]
        self.file		= None 

                            

    def start(self,attempt,maxattempts = 5) -> bool:
        if self.gprsStatus():
            print("GPRS IS ALREADY CONNECTED")
            return True
        try:
            return cellular.gprs(self.provider, "", "")
        except RuntimeError as e:
            print("Faild To init: {} ".format(e))
            cellular.reset()
            if attempt < maxattempts:
                attempt += 1
                return self.start(attempt)
            time.sleep(60)
            machine.reset()
            return True
        except Exception as ex:
            if str(ex).endswith("ETIMEDOUT"):
                print("Timed Out: ",ex)
                cellular.reset()
                machine.reset()
            else:
                print("Exception occured at init: ",ex)
                return True

    def stop(self):
        cellular.gprs(False)

    def gprsStatus(self) -> bool:
        try:
            return cellular.gprs()
        except RuntimeError as e:
            return False 
        return cellular.gprs()

    def connect(self, host:str = "", port = 443) -> socket:
            if host == "":
                host = self.host
            if port == None:
                port = self.port 

            print("IP", socket.get_local_ip(), "Host",host)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            addr_info = socket.getaddrinfo(host, port)
            s.connect(addr_info[0][4])
            file = s.makefile("rb")
            self.file = file
            if port == 443:
                s = ssl.wrap_socket(s)
            return s
    




    """
        This function is used to send a HTTP POST request
        
        path:   The url path afeter the host for Example: test.com/testing/1 -> /testing/1 is the path!
        data:   Any python object that can be deserailized
        auth:   HTTP Authorization string
        socket: An active Socket
        
        
        Thoughts:
            - No realitivly easy Aysnc functionality built in
            - Will requires using vairble buffer size (Prolly depends on network strength)
            - 130byte buffer is the maximum Atleast for this A9G board and accessories
            - HTTP GET will prolly use Socket.readline() I didnt see nothing on "Short Reads" from import file
            - And Prolly need to do it by chunks 
    """
    def post(self,
             path:str,
             data:dict,
             auth:str = "",
             host:str = "",
             quantity:int = 1,
             interval:int = 0,
             socket:socket = None
        ) -> str:
        if auth == "":
            auth = self.auth
        if host == "":
            host = self.host
        if socket is None:
            socket = self.connect(host = host)
        request = self.formRequest(path, data, auth, host)    
        try:
            while quantity > 0:
                socket.write(request)
                print("Posted Location: {} ".format(quantity))
                quantity -= 1
                time.sleep(interval)
            response = socket.read()
            socket.close()
            return response 
        except OSError as e:
            if str(e) == "-256":
                print("Socket Closed:{} \n\n Reconnecting To:{}".format(e,host))
                return self.post(path=path,data=data,auth=auth,quantity=quantity)
            print(e)
        


    def formRequest(self,path,data, auth, host) -> str:
        dataString = "" 
        try:
            dataString = ujson.dumps(data)
        except Exception as e:
            print("Error Deserializing Python Object",e)
        dataLength = len(dataString)
        print(dataString)
        request = (
            "POST {} HTTP/1.1\r\n"
            "Host: {}\r\n"
            "Authorization: {}\r\n"
            "Connection:keep-alive\r\n"
            "Content-Length: {}\r\n\r\n"
            "{}").format(
            path,
            host,
            auth,
            dataLength,
            dataString
        )
        return request

