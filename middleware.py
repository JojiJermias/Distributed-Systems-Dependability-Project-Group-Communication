# Bauer, Biregger, Chmel, Jermias
import logging
import select
import socket
import time
import json
from threading import Thread

# maximum payload size
BUFFER_SIZE = 1024

class Middleware:
    def __init__(self, peer_id, peer_list, port):
        self.seq_num = 0
        self.peer_id = peer_id
        self.peer_list = peer_list
        self.ip = "127.0.0.1"
        self.port = port
        # Create a datagram socket
        self.listening_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
        # Bind to address and ip
        self.listening_socket.bind((self.ip, port))
        self.message = None
        self.output = None

    def calculate_checksum(self, data):
        # Initialize the checksum
        sum = 0
        # Loop through the data by 2 bytes at a time
        for i in range(0, len(data), 2):
            # Get 2 bytes of data
            word = data[i: i + 2]
            # If the data length is odd and we have reached the last byte
            if (i + 2) > len(data):
                word += b'\x00'
            # Add the data to the sum
            sum += int.from_bytes(word, byteorder='big')
        # Handle overflow by wrapping the sum around
        sum = (sum >> 16) + (sum & 0xFFFF)
        sum += (sum >> 16)
        # Return the one's complement of the sum
        return (~sum) & 0xFFFF

    def verify_checksum(self, data, received_checksum):
        # Calculate the checksum of the data
        calculated_checksum = self.calculate_checksum(data)
        # Return whether the calculated checksum matches the given checksum
        return calculated_checksum == received_checksum

    # for error injection
    def toggle_bit(self, payload, bit_index):
        payload_bytes = bytearray(payload.encode())
        byte_index = bit_index // 8
        bit_offset = bit_index % 8
        # toggle bit at specified index
        payload_bytes[byte_index] ^= (1 << bit_offset)
        modified_payload = payload_bytes.decode()
        return modified_payload

    def send(self, payload):
        self.message = None
        # create a sender socket
        sending_socket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)

        acks_recv = self.send_all(sending_socket, payload)
        sending_socket.close()

        # mechanism for 'all or nothing' principle
        # message is only printed if ACKs from each Peer
        # message_counter for the case of error injection
        if acks_recv == len(self.peer_list) or message_counter == len(self.peer_list):
            for m in recv_messages:
                self.message = m
                logging.info(m)
                break
        else:
            self.message = ("Message was not delivered due to a communication error")

    def send_all(self, socket, payload):
        acks_recv = 0
        # iterative sending
        for i in self.peer_list:
            retries = 3
            self.output = None
            recv_address = (self.ip, i[1])
            while retries >= 0:
                try:
                    msgID = str(self.peer_id) + str(self.seq_num)

                    msg = json.dumps({'msgID': msgID, 'peerID': self.peer_id, 'msg': payload}).encode()
                    # Calculate the checksum of the message
                    calculated_checksum = self.calculate_checksum(msg)
                    # Send the message and checksum to the receiver
                    socket.sendto(msg + calculated_checksum.to_bytes(2, byteorder='big'), recv_address)
                    socket.setblocking(False)
                    ready = select.select([socket], [], [], 3)
                    if ready[0]:
                        recv_ack = socket.recvfrom(BUFFER_SIZE)
                        self.output = recv_ack[0].decode()
                        logging.info(recv_ack[0].decode())
                        acks_recv += 1
                        # waiting time between next send (1sec)
                        time.sleep(1)
                    elif not ready[0]:
                        raise Exception('No ACK received.')
                    break
                # if error --> don't break out of loop and retry
                except:
                    self.output = ("trying to reach", i, "retries left:", retries)
                    logging.info("trying to reach %s, retries left: %s", i, retries)
                    retries = retries - 1
                    time.sleep(1)
            # increment sequence number after each sent message
            self.seq_num = self.seq_num + 1
        return acks_recv

    def receive(self, error_message_id=None, error_bit_index=None):
        global recv_messages
        global message_counter
        recv_messages = set()
        message_counter = 0
        while True:
            # Receive the message and checksum from the sender
            bytesAddressPair = self.listening_socket.recvfrom(BUFFER_SIZE)
            address = bytesAddressPair[1]
            message = bytesAddressPair[0][:-2]
            received_checksum = int.from_bytes(bytesAddressPair[0][-2:], byteorder='big')

            # Error Injection
            if error_message_id is not None and error_bit_index is not None:
                actual_message = json.loads(message.decode())
                if int(actual_message['msgID']) == error_message_id:
                    modified_message = self.toggle_bit(actual_message['msg'], int(error_bit_index))
                    message = json.dumps({'msgID': actual_message['msgID'], 'peerID': actual_message['peerID'],
                                          'msg': modified_message}).encode()
                    logging.info(message.decode())

            # Verify the checksum of the received message
            if self.verify_checksum(message, received_checksum):
                message = json.loads(message.decode())

                # Sending a reply to client
                recv_ack = json.dumps({'msgID': message['msgID'], 'peerID': self.peer_id, 'msg': 'ACK'}).encode()
                logging.info(
                    "Peer-ACK: MessageID={} PeerID={} Port={} ".format(message['msgID'], self.peer_id, self.port))
                self.listening_socket.sendto(recv_ack, address)
                message_counter += 1

                # Agreement
                # if message not in receiving buffer --> add it
                # & if message was not self delivered --> send to other peers
                if message['msg'] not in recv_messages:
                    recv_messages.add(message['msg'])
                    if message['peerID'] != self.peer_id:
                        Thread(target=self.send, args=(message['msg'],)).start()

            
            else:
                self.output = "MessageID={} discarded (Incorrect Checksum)".format(error_message_id)
                logging.info("MessageID={} discarded (Incorrect Checksum)".format(error_message_id))
