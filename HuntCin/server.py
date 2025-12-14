"""
HuntCin - Server (Terceira Etapa)
Servidor UDP multi-cliente com transmissão confiável em camada de aplicação (RDT 3.0 - alternating bit).
Características:
 - Suporta múltiplos clientes (cada cliente é um processo com porta única).
 - Login / logout.
 - Comandos: move <up/down/left/right>, hint, suggest.
 - Rodadas temporizadas com broadcast de início e estado.
 - RDT stop-and-wait por cliente (alternating-bit).
"""

import socket
import threading
import time
import random
import traceback

# --- Configurações ---
TIMEOUT = 3.0
BUFFER_SIZE = 4096
ROUND_TIME = 30.0 # Duração da rodada em segundos
GRID_W, GRID_H = 3, 3
START_POS = (1, 1)

ACK0 = b'ACK0'
ACK1 = b'ACK1'

# --- RDT Utils ---
def make_pkt(seq, data):
    # Empacota: "0|Dados" ou "1|Dados"
    return str(seq).encode() + b'|' + data

def extract_pkt(packet):
    # Tenta separar pelo pipe '|'
    sep = packet.find(b'|')
    if sep == -1: return None, packet
    try:
        return int(packet[:sep].decode()), packet[sep+1:]
    except:
        return None, packet

def make_ack(seq):
    return ACK0 if seq == 0 else ACK1

# --- Estado do Servidor ---
HOST = "127.0.0.1"
PORT = 62451 

server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server.bind((HOST, PORT))
print(f"Servidor HuntCin iniciado em {HOST}:{PORT}")

# Cadeado (RLock) pra evitar que threads mexam na lista de clientes ao mesmo tempo
clients_lock = threading.RLock()

clients = {} 
player_scores = {}
running = True
current_treasure = None 

def ensure_client(addr):
    # Garante que o cliente existe no dicionário antes de tentar acessar
    with clients_lock:
        if addr not in clients:
            clients[addr] = {
                "name": None,
                "pos": START_POS,
                "online": False,
                "hint_used": False,
                "suggest_used": False,
                "last_command": None,
                "expected_seq_recv": 0, # O que espera receber (0 ou 1)
                "next_seq_send": 0, # O que vai enviar (0 ou 1)
                "ack_events": {0: threading.Event(), 1: threading.Event()} # Gatilhos pra acordar a thread
            }

def reliable_send(addr, msg_str):
    """Envia mensagem RDT para o cliente e aguarda ACK."""
    ensure_client(addr)
    payload = msg_str.encode()
    
    with clients_lock:
        if addr not in clients: return False
        seq = clients[addr]["next_seq_send"]
        ack_ev = clients[addr]["ack_events"][seq]
        ack_ev.clear() # Limpa o evento

    pkt = make_pkt(seq, payload)
    
    for i in range(5): 
        try:
            server.sendto(pkt, addr)
        except:
            pass
            
        if ack_ev.wait(TIMEOUT):
            with clients_lock:
                if addr in clients:
                    # Recebeu ACK! Inverte o bit (0->1 ou 1->0) pra proxima msg
                    clients[addr]["next_seq_send"] = 1 - seq
            return True
        print(f"[RDT] Timeout aguardando ACK{seq} de {addr} (Tentativa {i+1})")
    
    print(f"[RDT] Falha de envio para {addr}. Cliente pode estar offline.")
    return False

def receiver_thread():
    """Fica ouvindo a porta UDP o tempo todo."""
    print("[THREAD] Receptor RDT iniciado.")
    while running:
        try:
            packet, addr = server.recvfrom(BUFFER_SIZE)
        except:
            continue
        
        ensure_client(addr)
        
        # 1. É ACK?
        if packet == ACK0 or packet == ACK1:
            bit = 0 if packet == ACK0 else 1
            with clients_lock:
                if addr in clients:
                    # Acorda a função reliable_send que está travada no wait()
                    clients[addr]["ack_events"][bit].set()
            continue

        # 2. É DADO?
        seq, data = extract_pkt(packet)
        if seq is not None:
            # Envia ACK IMEDIATAMENTE
            ack_pkt = make_ack(seq)
            server.sendto(ack_pkt, addr)

            expected = 0
            with clients_lock:
                expected = clients[addr]["expected_seq_recv"]
            
            # Só processa se for a sequência exata que esperava (evita duplicatas)
            if seq == expected:
                with clients_lock:
                    clients[addr]["expected_seq_recv"] = 1 - expected
                
                try:
                    msg = data.decode()
                    # Processa em thread separada para não bloquear o receptor
                    threading.Thread(target=handle_msg, args=(addr, msg), daemon=True).start()
                except:
                    pass
            else:
                # Se for duplicado, o ACK já foi enviado acima. Apenas ignoramos o processamento.
                pass

def get_hint_text(px, py, tx, ty):
    if ty > py: return "O tesouro está mais acima."
    if ty < py: return "O tesouro está mais abaixo."
    if tx > px: return "O tesouro está mais à direita."
    if tx < px: return "O tesouro está mais à esquerda."
    return "Você está em cima do tesouro!"

def get_suggestion_text(px, py, tx, ty):
    # Retorna tupla: (direção, distancia)
    if ty > py: return "move up", ty - py
    if ty < py: return "move down", py - ty
    if tx > px: return "move right", tx - px
    if tx < px: return "move left", px - tx
    return None, 0

def handle_msg(addr, msg):
    """Processa a lógica do jogo."""
    global current_treasure
    
    # PEQUENO DELAY CRÍTICO: Dá tempo do cliente receber o ACK do comando
    # antes de recebermos a resposta do servidor.
    time.sleep(0.1) 

    try:
        parts = msg.strip().split()
        if not parts: return
        cmd = parts[0].lower()
        
        print(f"[CMD] {addr}: {msg}")

        # --- LOGIN ---
        if cmd == "login":
            if len(parts) < 2:
                reliable_send(addr, "ERRO: Use login <nome>")
                return
            nome = " ".join(parts[1:]).strip()
            
            online = False
            with clients_lock:
                online = clients[addr]["online"]

            if online:
                reliable_send(addr, "ERRO: Você já está logado.")
                return

            with clients_lock:
                for c in clients.values():
                    if c["online"] and c["name"] == nome:
                        reliable_send(addr, f"ERRO: O nome '{nome}' já está em uso.")
                        return

                clients[addr]["name"] = nome
                clients[addr]["online"] = True
                clients[addr]["pos"] = START_POS
                player_scores.setdefault(nome, 0)
            
            reliable_send(addr, "LOGIN SUCESSO: Você está online!")
            broadcast(f"[Servidor] {nome} entrou no jogo.")

        # --- LOGOUT ---
        elif cmd == "logout":
            online = False
            with clients_lock:
                online = clients[addr]["online"]

            if not online:
                reliable_send(addr, "ERRO: Você não está logado.")
                return
            
            name = None
            with clients_lock:
                name = clients[addr]["name"]
                clients[addr]["online"] = False
            reliable_send(addr, "logout efetuado")
            if name: broadcast(f"[Servidor] {name} saiu do jogo.")

        # --- MOVE ---
        elif cmd == "move":
            # VALIDAÇÃO NO SERVIDOR
            online = False
            with clients_lock:
                online = clients[addr]["online"]
            
            if not online:
                reliable_send(addr, "ERRO: Faça login primeiro.")
                return

            direction = parts[1].lower() if len(parts) > 1 else ""
            if direction not in ["up", "down", "left", "right"]:
                reliable_send(addr, "ERRO: Direção inválida.")
                return

            with clients_lock:
                clients[addr]["last_command"] = f"move {direction}"
            # O servidor não responde imediatamente ao move (só ACK), espera a rodada.

        # --- HINT ---
        elif cmd == "hint":
            online = False
            with clients_lock:
                online = clients[addr]["online"]

            if not online:
                reliable_send(addr, "ERRO: Faça login primeiro.")
                return
            
            used = False
            with clients_lock:
                if clients[addr]["hint_used"]: used = True
                else: clients[addr]["hint_used"] = True
                
            if used:
                reliable_send(addr, "ERRO: Você já usou sua dica nesta partida.")
                return

            px, py = (0,0)
            with clients_lock: px, py = clients[addr]["pos"]

            if current_treasure:
                tx, ty = current_treasure
                texto = get_hint_text(px, py, tx, ty)
                reliable_send(addr, f"DICA: {texto}")
            else:
                reliable_send(addr, "ERRO: Jogo não iniciado.")

        # --- SUGGEST ---
        elif cmd == "suggest":
            online = False
            with clients_lock:
                online = clients[addr]["online"]
            
            if not online:
                reliable_send(addr, "ERRO: Faça login primeiro.")
                return

            used = False
            with clients_lock:
                if clients[addr]["suggest_used"]: used = True
                else: clients[addr]["suggest_used"] = True

            if used:
                reliable_send(addr, "ERRO: Você já usou sua sugestão nesta partida.")
                return

            px, py = (0,0)
            with clients_lock: px, py = clients[addr]["pos"]

            if current_treasure:
                tx, ty = current_treasure
                # Pega a direção e a distância calculada
                sug, dist = get_suggestion_text(px, py, tx, ty)
                if sug:
                    reliable_send(addr, f"Sugestão: {sug} {dist} casas.")
                else:
                    reliable_send(addr, "Sugestão: Você já está no tesouro!")
            else:
                reliable_send(addr, "ERRO: Jogo não iniciado.")

    except Exception as e:
        print(f"Erro processando msg de {addr}: {e}")
        traceback.print_exc()

def broadcast(msg):
    targets = []
    with clients_lock:
        targets = [addr for addr, c in clients.items() if c["online"]]
    
    print(f"[BROADCAST] {msg}")
    for t in targets:
        # Manda em thread separada pra não travar o loop principal se um cliente demorar
        threading.Thread(target=reliable_send, args=(t, msg), daemon=True).start()

def reset_game_state():
    global current_treasure
    while True:
        tx = random.randint(1, GRID_W)
        ty = random.randint(1, GRID_H)
        if (tx, ty) != START_POS:
            current_treasure = (tx, ty)
            break
    
    with clients_lock:
        for c in clients.values():
            c["pos"] = START_POS
            c["hint_used"] = False
            c["suggest_used"] = False
            c["last_command"] = None

def game_loop():
    global round_num
    round_num = 0
    reset_game_state()
    
    print("[JOGO] Loop iniciado.")
    while running:
        round_num += 1
        print(f"\n>>> RODADA {round_num} (Tesouro em {current_treasure})")
        
        with clients_lock:
            for c in clients.values(): c["last_command"] = None
        
        # Avisa inicio da rodada
        broadcast(f"[Servidor] Início da rodada {round_num}! Envie seu movimento em {ROUND_TIME} segundos.")
        
        time.sleep(ROUND_TIME)
        
        broadcast("[Servidor] Calculando resultados...")
        
        msgs_log = []
        winners = []
        
        active_players = []
        with clients_lock:
            active_players = [(addr, c) for addr, c in clients.items() if c["online"]]
        
        for addr, client in active_players:
            cmd = client["last_command"]
            
            if not cmd:
                msgs_log.append(f"{client['name']} não enviou comando e foi eliminado desta rodada.")
                continue
            
            if cmd.startswith("move"):
                _, d = cmd.split()
                px, py = client["pos"]
                nx, ny = px, py
                
                if d == "up": ny += 1
                elif d == "down": ny -= 1
                elif d == "right": nx += 1
                elif d == "left": nx -= 1
                
                if not (1 <= nx <= GRID_W and 1 <= ny <= GRID_H):
                    msgs_log.append(f"{client['name']} bateu na parede em {client['pos']}.")
                else:
                    with clients_lock:
                        clients[addr]["pos"] = (nx, ny)
                    msgs_log.append(f"{client['name']} moveu para ({nx}, {ny}).")
                    
                    if (nx, ny) == current_treasure:
                        winners.append((addr, client["name"]))

        # Mostra onde todo mundo está
        with clients_lock:
            status_list = [f"{c['name']}{c['pos']}" for a, c in clients.items() if c["online"]]
        
        if status_list:
            broadcast("[Servidor] Estado atual: " + ", ".join(status_list))
        
        for m in msgs_log:
            broadcast(f"[Servidor] {m}")

        if not winners: 
            broadcast(f"[Servidor] Placar atual: {player_scores}")

        if winners:
            for w_addr, w_name in winners:
                msg_win = f"O jogador <{w_name}:{w_addr[1]}> encontrou o tesouro na posição {current_treasure}!"
                broadcast(msg_win)
                player_scores[w_name] += 1
                broadcast(f"[Servidor] Placar atual: {player_scores}")
            
            broadcast("[Servidor] Nova partida em 5 segundos...")
            time.sleep(5)
            reset_game_state()
        

if __name__ == "__main__":
    t_recv = threading.Thread(target=receiver_thread, daemon=True)
    t_recv.start()
    t_game = threading.Thread(target=game_loop, daemon=True)
    t_game.start()
    
    try:
        while True: time.sleep(1)
    except KeyboardInterrupt:
        running = False
        server.close()
        print("Servidor encerrado.")