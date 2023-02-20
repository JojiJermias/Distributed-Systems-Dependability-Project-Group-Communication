# Bauer, Biregger, Chmel, Jermias
import argparse
import json
import logging
import os
import re
from datetime import datetime
from threading import Thread
from middleware import Middleware

# Logging default path
path = 'log/'
path_set = False
date_time = datetime.now().strftime("%d.%m.%Y.%H-%M-%S")


def open_group_config(path):
    # use config file to create a peer list
    peer_list = []
    try:
        with open(path) as f:
            config = json.load(f)
            for c in config['group']:
                peer = (c['peer_id'], c['port'])
                peer_list.append(peer)
            return peer_list
    except FileNotFoundError:
        print("Please specify a valid group config file!")
        exit()


def get_menu_options():
    menu_options = ('0', '1', '2', '3')

    # generate the user interface
    while True:
        print()
        print('** MENU **')
        print('0 : exit')
        print('1 : listen for messages')
        print('2 : send message')
        print('3 : change logging path (current: ' + path + ')')
        print()

        action = input('Enter an option: ')

        if action in menu_options:
            return int(action)
        else:
            print()
            print('!! OPTION INVALID !!')


# Logging Path Viability Check
def checkpath(pathcheck):
    # Path or Directory must end with "/"
    if re.search("/$", pathcheck):
        path = pathcheck
        # If Directory does not exist
        if not os.path.exists(path):
            # check if Directory is creatable
            try:
                os.mkdir(path)
                os.rmdir(path)
                print("Creating " + os.path.abspath(path) + " as logging directory")
                return True
            except:
                print("Failed to create the specified directory. The specified Folder must match your"
                      " systems naming conventions. Continuing with default directory.")
                return False
        print("Your logs will be stored in: " + os.path.abspath(path))

    else:
        print("Invalid directory. The specified folder must end with '/'. Continuing with default directory.")
        return False


def show_output():
    while True:
        if middleware.output is not None:
            print(middleware.output)
            middleware.output = None
        if middleware.message is not None:
            break


def show_message():
    while True:
        if middleware.message == False:
            break
        if middleware.message is not None:
            print(middleware.message)
            middleware.message = None
            break


if __name__ == '__main__':
    # Terminal Argument Parser
    parser = argparse.ArgumentParser(description="DSD - Reliable Group Communication",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-i", "--peer-id", help="Specify the peerID", required=True)
    parser.add_argument("-p", "--port", help="Specify the listening port of the peer", required=True)
    parser.add_argument("-g", "--group-conf", help="Specify the path for the group configuration file", required=True)
    parser.add_argument("-dir", "--logging directory", help="Specify the Directory where the logs should be stored")
    parser.add_argument("--error-id", help="Error Injection - Specify the messageID of the message to be modified")
    parser.add_argument("--error-bit", help="Error Injection - Specify the bit index of the message bit to be toggled for the simulation of a single bit error")
    args = parser.parse_args()
    config = vars(args)

    # Configurations
    peer_list = open_group_config(config['group_conf'])
    for p in peer_list:
        # check for valid peer id and port
        if int(config['peer_id']) == p[0]:
            peer_id = int(config['peer_id'])
            if int(config['port']) == p[1]:
                port = int(config['port']) 
                break
        else:
            peer_id = None
            port = None

    if peer_id is None and port is None:
        print('Invalid peer ID and port combination!')
        exit()
    
    pathcheck = str(config['logging directory'])

    if config['logging directory']:
        if checkpath(pathcheck):
            path = pathcheck

    # check if error injection is enabled and set specifics
    error_message_id = int(config['error_id']) if config['error_id'] else None
    error_bit_index = int(config['error_bit']) if config['error_bit'] else None
    
    # create the peer middleware 
    middleware = Middleware(peer_id, peer_list, port)

    while True:
        action = get_menu_options()

        # exit program
        if action == 0:
            exit()

        # receiver
        if action == 1:

            # Create and set logging directory
            path_set = True
            if not os.path.exists(path):
                os.mkdir(path)
            # Set logging path
            logging.basicConfig(filename=path + peer_id.__str__() + "," + port.__str__() + "_" + date_time + ".log",
                                level=logging.INFO)
            print("Logging to: " + os.path.abspath(path))

            # Error Injection
            if error_message_id is not None and error_bit_index is not None:
                Thread(target=middleware.receive, args=(error_message_id, error_bit_index), daemon=True).start()
            else:
                Thread(target=middleware.receive, daemon=True).start()

            print("Peer {} is listening on port {}".format(peer_id, port))
            logging.info("Peer {} is listening on port {}".format(peer_id, port))

        # sender
        if action == 2:
            # Create and set logging directory
            path_set = True
            if not os.path.exists(path):
                os.mkdir(path)
            # Set logging path
            logging.basicConfig(filename=path + peer_id.__str__() + "," + port.__str__() + "_" + date_time + ".log",
                                level=logging.INFO)
            print("Logging to: " + os.path.abspath(path))

            print("This peer is sending")
            logging.info("This peer is sending")
            Thread(target=middleware.receive, daemon=True).start()
            payload = str(input('Please enter your message: '))
            Thread(target=middleware.send, args=(payload,)).start()

        # Change logging directory as long as peers did not start operating
        if action == 3:
            if not path_set:
                # Receive path from user input
                pathcheck = str(input('Please enter an alternative logging directory: '))
                # if the path input is valid assign it to the path variable
                if checkpath(pathcheck):
                    path = pathcheck
            else:
                # If the peer already operated, the path is set
                print("Path for this Session already set!")

            # Set message, so we don't get stuck in show_output() and show_message()
            middleware.message = False

        show_output()
        show_message()
