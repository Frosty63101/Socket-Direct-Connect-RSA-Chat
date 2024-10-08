import os
import re
import json
import socket
import random
import threading
import hashlib
import tkinter as tk
from dataclasses import dataclass
from typing import Optional


# ---------------------------- Data Classes ---------------------------- #

@dataclass
class PublicKey:
    N: int
    E: int


@dataclass
class PrivateKey:
    D: int


@dataclass
class RSAKeyPair:
    public_key: PublicKey
    private_key: PrivateKey


# ---------------------------- RSA Class ---------------------------- #

class RSA:
    """Class to handle RSA key generation, encryption, decryption, signing, and verification."""

    def __init__(self, key_length=2048):
        self.key_length = key_length
        self.key_pair: Optional[RSAKeyPair] = None

    def generate_keys(self):
        """Generates RSA key pair and stores it in the instance."""
        L = self.key_length
        while True:
            p = self.generate_prime_number(L // 2)
            q = self.generate_prime_number(L // 2)
            if p != q:
                n = p * q
                totient = self.lcm(p - 1, q - 1)
                while True:
                    e = random.randrange(2**16, 2**17)
                    if self.gcd(e, totient) == 1:
                        break
                d = self.modinv(e, totient)
                self.key_pair = RSAKeyPair(
                    public_key=PublicKey(N=n, E=e),
                    private_key=PrivateKey(D=d)
                )
                return

    @staticmethod
    def gcd(a, b):
        """Calculates the Greatest Common Divisor (GCD) of two numbers."""
        while b != 0:
            a, b = b, a % b
        return a

    @staticmethod
    def lcm(a, b):
        """Calculates the Least Common Multiple (LCM) of two numbers."""
        return abs(a * b) // RSA.gcd(a, b)

    @staticmethod
    def xgcd(a, b):
        """Extended Euclidean Algorithm."""
        prevx, x = 1, 0
        prevy, y = 0, 1
        while b != 0:
            q = a // b
            x, prevx = prevx - q * x, x
            y, prevy = prevy - q * y, y
            a, b = b, a % b
        return a, prevx, prevy

    @staticmethod
    def modinv(a, m):
        """Calculates the modular inverse of a modulo m."""
        g, x, _ = RSA.xgcd(a, m)
        if g != 1:
            raise Exception('Modular inverse does not exist')
        else:
            return x % m

    @staticmethod
    def is_prime(n, k=128):
        """Miller-Rabin primality test."""
        if n in (2, 3):
            return True
        if n <= 1 or n % 2 == 0:
            return False
        s, r = 0, n - 1
        while r % 2 == 0:
            s += 1
            r //= 2
        for _ in range(k):
            a = random.randrange(2, n - 1)
            x = pow(a, r, n)
            if x not in (1, n - 1):
                for __ in range(s - 1):
                    x = pow(x, 2, n)
                    if x == n - 1:
                        break
                else:
                    return False
        return True

    def generate_prime_number(self, length):
        """Generates a prime number of specified bit length."""
        while True:
            p = random.getrandbits(length)
            p |= (1 << length - 1) | 1  # Ensure p is odd and has the correct bit length
            if self.is_prime(p):
                return p

    def encrypt(self, message, public_key):
        """Encrypts a message using the recipient's public key."""
        return [pow(ord(char), public_key.E, public_key.N) for char in message]

    def decrypt(self, encrypted_message):
        """Decrypts an encrypted message using the private key."""
        if not self.key_pair:
            raise Exception('Key pair not generated')
        return ''.join([chr(pow(char_code, self.key_pair.private_key.D, self.key_pair.public_key.N))
                        for char_code in encrypted_message])

    @staticmethod
    def create_hash(message):
        """Creates a SHA-256 hash of the message."""
        return hashlib.sha256(message.encode()).hexdigest()

    def sign(self, message):
        """Signs a message using the private key."""
        if not self.key_pair:
            raise Exception('Key pair not generated')
        hash_message = self.create_hash(message)
        return pow(int(hash_message, 16), self.key_pair.private_key.D, self.key_pair.public_key.N)

    def verify(self, message, signature, public_key):
        """Verifies a message signature using the sender's public key."""
        hash_message = self.create_hash(message)
        hash_from_signature = pow(signature, public_key.E, public_key.N)
        return int(hash_message, 16) == hash_from_signature


# ---------------------------- Chat Application Class ---------------------------- #

class ChatApp:
    """Main class for the RSA Chat Application."""

    def __init__(self):
        # RSA instance
        self.rsa = RSA()

        # Networking
        self.client_socket = None
        self.server_socket = None
        self.other_public_key: Optional[PublicKey] = None
        self.is_client = False
        self.header_size = 10
        self.port = 5000  # Default port

        # GUI
        self.window = tk.Tk()
        self.window.title("RSA Chat")
        self.window.geometry("1000x500")
        self.setup_gui()

        # Paths
        self.stored_keys_file = os.path.join(os.getenv('LOCALAPPDATA') or '.', 'storedKeys.json')

    # ---------------------------- GUI Setup ---------------------------- #

    def setup_gui(self):
        """Sets up the GUI components."""
        button_width = 15
        entry_width = 20
        ip_entry_width = 30

        # Row 0: Key Generation and Storage
        tk.Button(self.window, text="Load Stored Keys", command=self.load_stored_keys,
                    width=button_width).grid(row=0, column=0, padx=5, pady=5)
        tk.Button(self.window, text="Generate New Keys", command=self.generate_new_keys,
                    width=button_width).grid(row=0, column=1, padx=5, pady=5)
        tk.Label(self.window, text="(Press one of the buttons to initialize keys)").grid(row=0, column=2, padx=5, pady=5)
        tk.Button(self.window, text="Send Public Key", command=self.send_public_key,
                    width=button_width).grid(row=0, column=3, padx=5, pady=5)
        self.port_entry = tk.Entry(self.window, width=entry_width)
        self.port_entry.grid(row=0, column=4, padx=5, pady=5)
        self.port_entry.insert(0, str(self.port))

        # Row 1: Display E, N, D
        tk.Label(self.window, text="E: ").grid(row=1, column=0, padx=5, pady=5)
        self.e_entry = tk.Entry(self.window, width=entry_width, state='readonly')
        self.e_entry.grid(row=1, column=1, padx=5, pady=5)
        tk.Label(self.window, text="N: ").grid(row=1, column=2, padx=5, pady=5)
        self.n_entry = tk.Entry(self.window, width=entry_width, state='readonly')
        self.n_entry.grid(row=1, column=3, padx=5, pady=5)
        tk.Label(self.window, text="D: ").grid(row=1, column=4, padx=5, pady=5)
        self.d_entry = tk.Entry(self.window, width=entry_width, state='readonly')
        self.d_entry.grid(row=1, column=5, padx=5, pady=5)

        # Row 2: Server and Client Controls
        tk.Button(self.window, text="Host", command=self.start_server,
                    width=button_width).grid(row=2, column=0, padx=5, pady=5)
        tk.Label(self.window, text="Your IP:").grid(row=2, column=1, padx=5, pady=5)
        self.host_ip_entry = tk.Entry(self.window, width=ip_entry_width, state='readonly')
        self.host_ip_entry.grid(row=2, column=2, padx=5, pady=5)
        tk.Label(self.window, text="Server IP:").grid(row=2, column=3, padx=5, pady=5)
        self.server_ip_entry = tk.Entry(self.window, width=ip_entry_width)
        self.server_ip_entry.grid(row=2, column=4, padx=5, pady=5)
        tk.Button(self.window, text="Connect", command=self.connect_to_server,
                    width=button_width).grid(row=2, column=5, padx=5, pady=5)

        # Row 3: Chat Display and Nickname
        self.chat_text = tk.Text(self.window, height=10, width=65, state='disabled')
        self.chat_text.grid(row=3, column=0, columnspan=5, padx=5, pady=5)
        tk.Label(self.window, text="Nickname:").grid(row=3, column=5, padx=5, pady=5)
        self.nickname_entry = tk.Entry(self.window, width=20)
        self.nickname_entry.grid(row=3, column=6, columnspan=2, padx=5, pady=5)
        self.nickname_entry.insert(tk.END, "Anonymous")

        # Row 4: Message Entry and Send Button
        tk.Label(self.window, text="Your Message:").grid(row=4, column=0, padx=5, pady=5)
        self.message_entry = tk.Entry(self.window, width=55)
        self.message_entry.grid(row=4, column=1, columnspan=3, padx=5, pady=5)
        tk.Button(self.window, text="Send", command=self.send_message,
                    width=button_width).grid(row=4, column=4, padx=5, pady=5)

        # Row 5: Disconnect Button
        tk.Button(self.window, text="Disconnect", command=self.disconnect,
                    width=button_width).grid(row=5, column=0, padx=5, pady=5)

        # Bind Enter key to send message
        self.window.bind('<Return>', lambda event: self.send_message())

    # ---------------------------- Key Management ---------------------------- #

    def generate_new_keys(self):
        """Generates new RSA keys and updates the display."""
        self.rsa.generate_keys()
        self.store_keys()
        self.update_key_display()
        self.update_chat("New keys generated.")

    def load_stored_keys(self):
        """Loads stored RSA keys from file and updates the display."""
        try:
            with open(self.stored_keys_file, 'r') as f:
                keys = json.load(f)
                public_key = PublicKey(N=keys['N'], E=keys['E'])
                private_key = PrivateKey(D=keys['D'])
                self.rsa.key_pair = RSAKeyPair(public_key=public_key, private_key=private_key)
                self.update_key_display()
                self.update_chat("Stored keys loaded.")
        except (FileNotFoundError, json.JSONDecodeError):
            self.update_chat("No stored keys found. Generating new keys...")
            self.generate_new_keys()

    def store_keys(self):
        """Stores the RSA keys to a file."""
        if self.rsa.key_pair:
            keys = {
                'N': self.rsa.key_pair.public_key.N,
                'E': self.rsa.key_pair.public_key.E,
                'D': self.rsa.key_pair.private_key.D
            }
            with open(self.stored_keys_file, 'w') as f:
                json.dump(keys, f)
            self.update_chat("Keys stored successfully.")

    def update_key_display(self):
        """Updates the GUI entries with the current keys."""
        if self.rsa.key_pair:
            self.e_entry.config(state='normal')
            self.n_entry.config(state='normal')
            self.d_entry.config(state='normal')

            self.e_entry.delete(0, tk.END)
            self.n_entry.delete(0, tk.END)
            self.d_entry.delete(0, tk.END)

            self.e_entry.insert(0, str(self.rsa.key_pair.public_key.E))
            self.n_entry.insert(0, str(self.rsa.key_pair.public_key.N))
            self.d_entry.insert(0, str(self.rsa.key_pair.private_key.D))

            self.e_entry.config(state='readonly')
            self.n_entry.config(state='readonly')
            self.d_entry.config(state='readonly')

    # ---------------------------- Networking ---------------------------- #

    def start_server(self):
        """Starts the server to listen for incoming connections."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        self.host_ip_entry.config(state='normal')
        self.host_ip_entry.delete(0, tk.END)
        self.host_ip_entry.insert(0, ip_address)
        self.host_ip_entry.config(state='readonly')
        try:
            self.port = int(self.port_entry.get())
            self.server_socket.bind((ip_address, self.port))
            self.server_socket.listen(1)
            self.update_chat(f"Server listening on {ip_address}:{self.port}")
            threading.Thread(target=self.accept_connections, daemon=True).start()
        except Exception as e:
            self.update_chat(f"Server error: {e}")

    def accept_connections(self):
        """Accepts incoming client connections."""
        try:
            if self.server_socket:
                conn, addr = self.server_socket.accept()
                self.update_chat(f"Connected to {addr}")
                self.client_socket = conn
                self.is_client = False
                self.start_listening_thread(conn)
                self.send_public_key()
        except Exception as e:
            self.update_chat(f"Connection error: {e}")

    def connect_to_server(self):
        """Connects to a server as a client."""
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        host = self.server_ip_entry.get()
        try:
            self.port = int(self.port_entry.get())
            self.client_socket.connect((host, self.port))
            self.update_chat(f"Connected to server {host}:{self.port}")
            self.is_client = True
            self.start_listening_thread(self.client_socket)
            self.send_public_key()
        except Exception as e:
            self.update_chat(f"Connection error: {e}")

    def start_listening_thread(self, sock):
        """Starts a thread to listen for incoming messages."""
        threading.Thread(target=self.listen_for_messages, args=(sock,), daemon=True).start()

    def listen_for_messages(self, sock):
        """Listens for incoming messages from the socket."""
        while True:
            try:
                full_message = b""
                new_msg = True
                msg_length = 0
                while True:
                    message = sock.recv(16)
                    if new_msg:
                        msg_length = int(message[:self.header_size])
                        new_msg = False
                    full_message += message
                    if len(full_message) - self.header_size == msg_length:
                        self.handle_received_message(full_message[self.header_size:].decode())
                        new_msg = True
                        full_message = b""
            except Exception as e:
                self.update_chat(f"Receiving error: {e}")
                break

    def send_data(self, data):
        """Sends data through the client socket."""
        if self.client_socket:
            message = data.encode()
            message_header = f"{len(message):<{self.header_size}}".encode()
            try:
                self.client_socket.sendall(message_header + message)
            except Exception as e:
                self.update_chat(f"Sending error: {e}")
        else:
            self.update_chat("Not connected to any client or server.")

    # ---------------------------- Message Handling ---------------------------- #

    def send_message(self):
        """Encrypts and sends a message to the connected client/server."""
        message = self.message_entry.get()
        if self.other_public_key and self.rsa.key_pair:
            signature = self.rsa.sign(message)
            encrypted_message = self.rsa.encrypt(message, self.other_public_key)
            nickname = self.nickname_entry.get() or "Anonymous"
            message_with_signature = {
                "nickname": nickname,
                "message": encrypted_message,
                "signature": signature
            }
            self.send_data(json.dumps(message_with_signature))
            self.update_chat(f"You: {message}")
            self.message_entry.delete(0, tk.END)
        else:
            self.update_chat("Encryption keys not exchanged.")

    def handle_received_message(self, message):
        """Handles a received message."""
        if message.startswith("KEYS:"):
            try:
                _, key_data = message.split(":", 1)
                N_str, E_str = key_data.split(",", 1)
                N = int(N_str)
                E = int(E_str)
                self.other_public_key = PublicKey(N=N, E=E)
                self.update_chat("Received public key.")
                if not self.is_client:
                    self.send_public_key()
            except ValueError as e:
                self.update_chat(f"Public key error: {e}")
        else:
            try:
                received_data = json.loads(message)
                encrypted_message = received_data["message"]
                signature = received_data["signature"]
                nickname = received_data.get("nickname", "Unknown")
                decrypted_message = self.rsa.decrypt(encrypted_message)
                if self.rsa.verify(decrypted_message, signature, self.other_public_key):
                    self.update_chat(f"{nickname}: {decrypted_message}")
                else:
                    self.update_chat("Signature verification failed.")
            except json.JSONDecodeError as e:
                self.update_chat(f"JSON decoding error: {e}")
            except Exception as e:
                self.update_chat(f"Message handling error: {e}")

    def send_public_key(self):
        """Sends the public key to the connected client/server."""
        if self.client_socket and self.rsa.key_pair:
            N = self.rsa.key_pair.public_key.N
            E = self.rsa.key_pair.public_key.E
            key_message = f"KEYS:{N},{E}"
            self.send_data(key_message)
            self.update_chat("Public key sent.")
        else:
            self.update_chat("Cannot send public key; no connection or keys not generated.")

    # ---------------------------- Utilities ---------------------------- #

    def update_chat(self, message):
        """Updates the chat display with a new message."""
        self.chat_text.config(state='normal')
        self.chat_text.insert(tk.END, f"{message}\n")
        self.chat_text.config(state='disabled')
        self.chat_text.see(tk.END)

    def disconnect(self):
        """Disconnects from the client/server and closes sockets."""
        if self.client_socket:
            self.client_socket.close()
            self.client_socket = None
            self.update_chat("Disconnected from client/server.")
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None
            self.update_chat("Server socket closed.")
        self.window.destroy()

    # ---------------------------- Run Application ---------------------------- #

    def run(self):
        """Runs the main application loop."""
        self.window.mainloop()


# ---------------------------- Main Execution ---------------------------- #

if __name__ == '__main__':
    app = ChatApp()
    app.run()
