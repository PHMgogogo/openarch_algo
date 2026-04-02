import socket
import subprocess
import sys
from typing import Literal, Optional, List, Tuple, Set


class PortChecker:
    def __init__(self):
        self.allocated_ports: Set[Tuple[int, str]] = set()

    def find_free_port(self, protocol: Literal["tcp", "udp"] = "tcp") -> int:
        """获取一个未使用的端口，协议可以是 tcp 或 udp"""
        sock_type = (
            socket.SOCK_STREAM if protocol.lower() == "tcp" else socket.SOCK_DGRAM
        )
        with socket.socket(socket.AF_INET, sock_type) as s:
            s.bind(("", 0))  # 让操作系统分配端口
            port = s.getsockname()[1]
        self.allocated_ports.add((port, protocol.lower()))
        return port

    def get_allocated_ports(self, protocol: Optional[str] = None) -> List[Tuple[int, str]]:
        """返回系统中所有已分配的端口（TCP/UDP 可选）"""
        ports = set()
        if sys.platform.startswith("linux") or sys.platform.startswith("darwin"):
            # Linux/macOS 使用 ss 或 netstat
            try:
                result = subprocess.run(["ss", "-tuna"], capture_output=True, text=True)
                lines = result.stdout.splitlines()
                for line in lines[1:]:
                    parts = line.split()
                    if len(parts) < 5:
                        continue
                    proto = parts[0].lower()
                    local_addr = parts[4]
                    if ":" in local_addr:
                        port_str = local_addr.split(":")[-1]
                        if port_str.isdigit():
                            port = int(port_str)
                            if protocol is None or proto.startswith(protocol.lower()):
                                ports.add((port, proto))
            except FileNotFoundError:
                # fallback to netstat
                result = subprocess.run(
                    ["netstat", "-tuna"], capture_output=True, text=True
                )
                lines = result.stdout.splitlines()
                for line in lines[2:]:
                    parts = line.split()
                    if len(parts) < 4:
                        continue
                    proto = parts[0].lower()
                    local_addr = parts[3]
                    if ":" in local_addr:
                        port_str = local_addr.split(":")[-1]
                        if port_str.isdigit():
                            port = int(port_str)
                            if protocol is None or proto.startswith(protocol.lower()):
                                ports.add((port, proto))
        elif sys.platform.startswith("win"):
            # Windows
            result = subprocess.run(["netstat", "-ano"], capture_output=True, text=True)
            lines = result.stdout.splitlines()
            for line in lines:
                if line.startswith("  TCP") or line.startswith("  UDP"):
                    parts = line.split()
                    proto = parts[0].lower()
                    local_addr = parts[1]
                    if ":" in local_addr:
                        port_str = local_addr.split(":")[-1]
                        if port_str.isdigit():
                            port = int(port_str)
                            if protocol is None or proto.startswith(protocol.lower()):
                                ports.add((port, proto))
        return list(ports)


# 示例
if __name__ == "__main__":
    pc = PortChecker()
    port_tcp = pc.find_free_port("tcp")
    port_udp = pc.find_free_port("udp")
    print("新分配的端口 TCP:", port_tcp, "UDP:", port_udp)
    print("系统中已分配端口:", pc.get_allocated_ports())
