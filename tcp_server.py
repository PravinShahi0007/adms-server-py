import socket
import threading
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def handle_client(client_socket, client_address):
    """Handle incoming TCP connection"""
    logger.info(f"New connection from {client_address}")
    
    try:
        # Read raw data
        data = client_socket.recv(4096)
        
        if data:
            logger.info(f"[{client_address[0]}] Received {len(data)} bytes")
            logger.info(f"[{client_address[0]}] Raw hex: {data.hex()}")
            
            # Try to decode as text
            try:
                text = data.decode('utf-8', errors='replace')
                logger.info(f"[{client_address[0]}] As text: {repr(text[:500])}")
            except:
                logger.info(f"[{client_address[0]}] Cannot decode as UTF-8")
            
            # Check for SSL/TLS handshake
            if data.startswith(b'\x16\x03'):
                tls_version = f"{data[1]}.{data[2]}"
                logger.info(f"[{client_address[0]}] TLS handshake detected (version {tls_version})")
                logger.info(f"[{client_address[0]}] ZKTeco device trying HTTPS/SSL connection")
                logger.warning(f"[{client_address[0]}] Device keeps trying SSL - please configure device to use HTTP instead")
                
                # Try different approaches to make device fallback
                # Option 1: Connection reset
                try:
                    # Send TCP RST to force connection close
                    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b'\x01\x00\x00\x00')
                    logger.info(f"[{client_address[0]}] Sent TCP RST to force reconnection")
                except:
                    pass
                return
            
            # Check for HTTP-like patterns
            if b'HTTP' in data or b'GET' in data or b'POST' in data:
                logger.info(f"[{client_address[0]}] Looks like HTTP request")
                # Simple HTTP response
                response = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK"
                client_socket.send(response)
                return
            
            # Check for ZKTeco patterns
            zkeco_patterns = [b'ZKECO', b'ATTLOG', b'iclock', b'SN=']
            for pattern in zkeco_patterns:
                if pattern in data:
                    logger.info(f"[{client_address[0]}] Found ZKTeco pattern: {pattern}")
            
            # Generic response for unknown protocols
            try:
                response = b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK"
                client_socket.send(response)
            except:
                logger.warning(f"[{client_address[0]}] Could not send response")
            
    except Exception as e:
        logger.error(f"Error handling client {client_address}: {e}")
    finally:
        client_socket.close()
        logger.info(f"Connection closed: {client_address}")

def start_tcp_server(port=8081):
    """Start TCP server to capture raw requests"""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind(('0.0.0.0', port))
        server_socket.listen(5)
        logger.info(f"TCP debug server listening on port {port}")
        
        while True:
            client_socket, client_address = server_socket.accept()
            
            # Handle each connection in a separate thread
            client_thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address)
            )
            client_thread.daemon = True
            client_thread.start()
            
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_tcp_server()