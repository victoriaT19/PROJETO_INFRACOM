"""
HuntCin - Server (Terceira Etapa)
Servidor UDP multi-cliente com transmissão confiável em camada de aplicação (RDT 3.0 - alternating bit).
Características:
 - Suporta múltiplos clientes (cada cliente é um processo com porta única).
 - Login / logout.
 - Comandos: move <up/down/left/right>, hint, suggest.
 - Rodadas temporizadas com broadcast de início e estado.
 - RDT stop-and-wait por cliente (alternating-bit).
 - PROB_PERDA = 0 por padrão (desative simulação de perdas). Ajuste se quiser testar robustez.
"""

import socket
import threading
import time
import random

# --- Configurações RDT / jogo ---
TIMEOUT = 2.0                 # timeout para retransmissões RDT
PROB_PERDA = 0.0              # probabilidade de perda simulada (0 = sem perda)
BUFFER_SIZE = 2048
ROUND_TIME = 10.0             # tempo de cada rodada (segundos)
GRID_W, GRID_H = 3, 3         # grid 3x3
START_POS = (1, 1)            # posição inicial (1,1) canto inferior esquerdo

# ACKs simples
ACK0 = b'ACK0'
ACK1 = b'ACK1'

# --- Utilitários RDT ---
def make_pkt(seq_num: int, data: bytes) -> bytes:
    """Cria um pacote com bit de sequência: b'0|payload' ou b'1|payload'."""
    return str(seq_num).encode() + b'|' + data

def extract_pkt(packet: bytes):
    """Extrai (seq_num, data). Se não houver '|', retorna (None, packet)."""
    sep = packet.find(b'|')
    if sep == -1:
        return None, packet
    try:
        seq = int(packet[:sep].decode())
        data = packet[sep+1:]
        return seq, data
    except Exception:
        return None, packet

def make_ack_bytes(seq_num: int) -> bytes:
    return ACK0 if seq_num == 0 else ACK1

def simulate_loss() -> bool:
    """Simula perda no envio para testar robustez. Pode ser desativada com PROB_PERDA = 0."""
    return random.random() < PROB_PERDA

# --- Estado do servidor ---
HOST = "0.0.0.0"
PORT = 5000

servidor = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
servidor.bind((HOST, PORT))
servidor.settimeout(0.5)  # timeout curto para permitir checagens periódicas

clients_lock = threading.Lock()
# clients: chave = (ip, port) ; valor = dict com infos do cliente
clients = {}

# pontuação acumulada por nome
player_scores = {}

# estado de rodada
round_lock = threading.Lock()
current_treasure = None
round_number = 0
running = True

# --- Funções que operam por cliente ---
def ensure_client_state(addr):
    """Garante que exista dicionário de estado para um client (endereço)."""
    with clients_lock:
        if addr not in clients:
            clients[addr] = {
                "name": None,
                "expected_seq_recv": 0,   # bit esperado ao receber deste cliente
                "next_seq_send": 0,      # bit a ser usado para enviar para este cliente
                "pos": START_POS,
                "online": False,
                "hint_used": False,
                "suggest_used": False,
                "last_command": None,    # comando enviado na rodada atual
                "last_active": time.time(),
                "ack_events": {0: threading.Event(), 1: threading.Event()},
            }

def reliable_send(addr, message_str):
    """
    Envia message_str (str) de forma confiável para client addr usando RDT stop-and-wait.
    Usa per-client alternating bit e um Event que é sinalizado pela thread de recebimento
    quando chega o ACK correspondente.
    """
    ensure_client_state(addr)
    payload = message_str.encode()
    while True:
        with clients_lock:
            client = clients.get(addr)
            if client is None:
                print(f"[RDT-ENVIAR] Cliente {addr} não existe mais, abortando envio.")
                return False
            seq = client["next_seq_send"]
            ack_event = client["ack_events"][seq]
            ack_event.clear()

        pkt = make_pkt(seq, payload)

        if simulate_loss():
            print(f"  [SIMULAÇÃO] (server->{addr}) Pacote {seq} PERDIDO (mensagem: {message_str})")
        else:
            try:
                servidor.sendto(pkt, addr)
            except Exception as e:
                print(f"[RDT-ENVIAR] Erro ao enviar para {addr}: {e}")

        # aguarda ACK do cliente com retransmissão até TIMEOUT
        got = ack_event.wait(TIMEOUT)
        if got:
            with clients_lock:
                client = clients.get(addr)
                if client:
                    client["next_seq_send"] = 1 - client["next_seq_send"]
                    client["last_active"] = time.time()
            return True
        else:
            print(f"  [RDT-ENVIAR] Timeout esperando ACK{seq} de {addr}. Reenviando...")

def send_ack_immediate(addr, seq_num):
    """Envia um ACK simples (pode ser perdido). Usado pelo receptor para confirmar pkt recebido."""
    ack = make_ack_bytes(seq_num)
    if simulate_loss():
        print(f"  [SIMULAÇÃO] (server->{addr}) ACK{seq_num} PERDIDO")
    else:
        servidor.sendto(ack, addr)

# --- Recepção: thread que processa tudo que chega ao socket ---
def receiver_thread():
    """
    Loop que recebe todos os pacotes UDP e faz:
    - se for ACK (ACK0/ACK1) => sinaliza o evento de ack do cliente correspondente
    - se for dado com header 'bit|payload' => processa de acordo com expected_seq_recv do cliente
    """
    global running
    print(f"[RECEPTOR] Thread de recepção iniciada na porta {PORT}.")
    while running:
        try:
            packet, addr = servidor.recvfrom(BUFFER_SIZE)
        except socket.timeout:
            continue
        except Exception as e:
            print(f"[RECEPTOR] Erro recvfrom: {e}")
            continue

        ensure_client_state(addr)

        # se for ACK puro (ACK0/ACK1)
        if packet == ACK0 or packet == ACK1:
            bit = 0 if packet == ACK0 else 1
            with clients_lock:
                client = clients.get(addr)
                if client:
                    ev = client["ack_events"].get(bit)
                    if ev:
                        ev.set()
            continue

        # caso contrário, tenta extrair pacote com header
        seq, data = extract_pkt(packet)
        if seq is None:
            print(f"[RECEPTOR] Pacote mal formatado de {addr}: {packet[:50]}...")
            continue

        with clients_lock:
            client = clients.get(addr)
            expected = client["expected_seq_recv"]

        if seq == expected:
            with clients_lock:
                client["expected_seq_recv"] = 1 - client["expected_seq_recv"]
                client["last_active"] = time.time()
            try:
                msg = data.decode()
            except Exception:
                msg = ""
            print(f"[RECEPTOR] De {addr} (seq={seq}): {msg}")
            send_ack_immediate(addr, seq)
            threading.Thread(target=handle_application_message, args=(addr, msg), daemon=True).start()
        else:
            print(f"[RECEPTOR] De {addr}: pacote seq={seq} duplicado/fora de ordem (esperado={expected}). Reenviando ACK do anterior.")
            send_ack_immediate(addr, 1 - expected)

# --- Lógica de aplicação: login/logout, comandos do jogo ---
def broadcast_message(message):
    """Envia message para todos os clientes online (reliable send por cliente)."""
    with clients_lock:
        addrs = [a for a, c in clients.items() if c["online"]]
    for addr in addrs:
        threading.Thread(target=reliable_send, args=(addr, message), daemon=True).start()

def handle_application_message(addr, msg):
    """
    Mensagens que o servidor espera dos clientes (strings):
      - login <nome>
      - logout
      - move <up/down/left/right>
      - hint
      - suggest
    Respostas de controle são enviadas via reliable_send (RDT).
    """
    ensure_client_state(addr)
    parts = msg.strip().split()
    if len(parts) == 0:
        return
    cmd = parts[0].lower()

    if cmd == "login" and len(parts) >= 2:
        nome = " ".join(parts[1:]).strip()
        with clients_lock:
            nomes = [c["name"] for c in clients.values() if c["online"] and c["name"]]
            if nome in nomes:
                print(f"[LOGIN] Tentativa de login com nome já existente: {nome} por {addr}")
                reliable_send(addr, f"ERRO: nome '{nome}' já está em uso.")
                return
            clients[addr]["name"] = nome
            clients[addr]["online"] = True
            clients[addr]["pos"] = START_POS
            clients[addr]["hint_used"] = False
            clients[addr]["suggest_used"] = False
            clients[addr]["last_command"] = None
            clients[addr]["last_active"] = time.time()
            player_scores.setdefault(nome, 0)
        print(f"[LOGIN] '{nome}' conectado de {addr}.")
        reliable_send(addr, "você está online!")
        broadcast_message(f"[Servidor] {nome}:{addr[1]} entrou no jogo.")

    elif cmd == "logout":
        with clients_lock:
            name = clients[addr]["name"]
            clients[addr]["online"] = False
            clients[addr]["last_command"] = None
        print(f"[LOGOUT] {name} ({addr}) desconectou.")
        reliable_send(addr, "logout efetuado.")
        broadcast_message(f"[Servidor] {name}:{addr[1]} saiu do jogo.")

    elif cmd == "move" and len(parts) == 2:
        direction = parts[1].lower()
        with clients_lock:
            if not clients[addr]["online"]:
                reliable_send(addr, "ERRO: você precisa estar online para mover.")
                return
            clients[addr]["last_command"] = f"move {direction}"
            clients[addr]["last_active"] = time.time()
        reliable_send(addr, f"Comando recebido: move {direction}")

    elif cmd == "hint":
        with clients_lock:
            if not clients[addr]["online"]:
                reliable_send(addr, "ERRO: precisa estar online para pedir hint.")
                return
            if clients[addr]["hint_used"]:
                reliable_send(addr, "ERRO: você já usou sua dica nesta partida.")
                return
            clients[addr]["hint_used"] = True
        with round_lock:
            if current_treasure is None:
                reliable_send(addr, "ERRO: sem jogo em andamento.")
                return
            tx, ty = current_treasure
        px, py = clients[addr]["pos"]
        if ty > py:
            texto = "O tesouro está mais acima."
        elif ty < py:
            texto = "O tesouro está mais abaixo."
        elif tx > px:
            texto = "O tesouro está mais à direita."
        elif tx < px:
            texto = "O tesouro está mais à esquerda."
        else:
            texto = "O tesouro está exatamente na sua posição!"
        reliable_send(addr, texto)

    elif cmd == "suggest":
        with clients_lock:
            if not clients[addr]["online"]:
                reliable_send(addr, "ERRO: precisa estar online para pedir suggestion.")
                return
            if clients[addr]["suggest_used"]:
                reliable_send(addr, "ERRO: você já usou sua sugestão nesta partida.")
                return
            clients[addr]["suggest_used"] = True
        with round_lock:
            if current_treasure is None:
                reliable_send(addr, "ERRO: sem jogo em andamento.")
                return
            tx, ty = current_treasure
        px, py = clients[addr]["pos"]
        suggestion = None
        if ty > py:
            suggestion = "move up"
        elif ty < py:
            suggestion = "move down"
        elif tx > px:
            suggestion = "move right"
        elif tx < px:
            suggestion = "move left"
        else:
            suggestion = "Você já está no tesouro!"
        reliable_send(addr, f"Sugestão: {suggestion}")

    else:
        reliable_send(addr, "ERRO: comando inválido ou formato incorreto.")

# --- Funções de jogo (controle de rodada e validação de movimento) ---
def random_treasure_position():
    """Sorteia posição do tesouro entre (1..3,1..3) exceto START_POS."""
    while True:
        x = random.randint(1, GRID_W)
        y = random.randint(1, GRID_H)
        if (x, y) != START_POS:
            return (x, y)

def validate_and_apply_move(name_addr_pair, direction):
    """Valida e aplica o movimento se dentro do grid."""
    addr, name = name_addr_pair
    with clients_lock:
        client = clients.get(addr)
        if not client or not client["online"]:
            return f"{name} não está online."
        px, py = client["pos"]

    dx = dy = 0
    if direction == "up":
        dy = 1
    elif direction == "down":
        dy = -1
    elif direction == "left":
        dx = -1
    elif direction == "right":
        dx = 1
    else:
        return f"{name}: comando de movimento inválido."

    nx, ny = px + dx, py + dy
    if not (1 <= nx <= GRID_W and 1 <= ny <= GRID_H):
        return f"{name}: movimento fora do grid. Posição permanece ({px},{py})."
    with clients_lock:
        clients[addr]["pos"] = (nx, ny)
    return f"{name} movido para ({nx},{ny})."

def round_loop():
    """Loop que executa rodadas sequenciais do jogo enquanto running==True."""
    global current_treasure, round_number
    print("[JOGO] Iniciando loop de rodadas.")
    while running:
        round_number += 1
        with round_lock:
            current_treasure = random_treasure_position()
        print(f"[JOGO] Rodada {round_number} começando. Tesouro sorteado.")
        with clients_lock:
            for c in clients.values():
                c["last_command"] = None
        broadcast_message(f"[Servidor] Início da rodada {round_number}! Envie seu movimento em {ROUND_TIME} segundos.")
        start = time.time()
        while time.time() - start < ROUND_TIME:
            time.sleep(0.2)
        print(f"[JOGO] Rodada {round_number} encerrando. Processando comandos.")
        eliminados = []
        resultados = []
        winners = []
        with clients_lock:
            active_clients = [(addr, c["name"]) for addr, c in clients.items() if c["online"]]
        for addr, name in active_clients:
            with clients_lock:
                cmd = clients[addr]["last_command"]
            if cmd is None:
                eliminados.append((addr, name))
            else:
                if cmd.startswith("move"):
                    _, direction = cmd.split(maxsplit=1)
                    res = validate_and_apply_move((addr, name), direction)
                    resultados.append(res)
        with clients_lock:
            estado = ", ".join([f"{c['name']}({c['pos'][0]},{c['pos'][1]})"
                                for c in clients.values() if c["online"]])
        broadcast_message(f"[Servidor] Estado atual: {estado}")
        with clients_lock:
            for addr, c in clients.items():
                if c["online"] and c["pos"] == current_treasure:
                    winners.append((addr, c["name"]))
        if winners:
            for addr, name in winners:
                msg = f"O jogador {name}:{addr[1]} encontrou o tesouro na posição {current_treasure}!"
                print(f"[JOGO] {msg}")
                broadcast_message(f"[Servidor] {msg}")
                player_scores[name] = player_scores.get(name, 0) + 1
            broadcast_message(f"[Servidor] Placar parcial: {player_scores}")
            time.sleep(2)
        else:
            if eliminados:
                names_el = ", ".join([n for (_, n) in eliminados])
                broadcast_message(f"[Servidor] Eliminados desta rodada: {names_el}")
            for r in resultados:
                broadcast_message(f"[Servidor] {r}")
            time.sleep(1)

# --- Inicialização ---
if __name__ == "__main__":
    print("Servidor HuntCin (RDT 3.0) iniciando.")
    print(f"Aguardando clientes em {HOST}:{PORT} ...")
    t = threading.Thread(target=receiver_thread, daemon=True)
    t.start()
    game_thread = threading.Thread(target=round_loop, daemon=True)
    game_thread.start()

    try:
        while True:
            cmd = input("Comando servidor (type 'quit' to stop): ").strip().lower()
            if cmd == "quit":
                print("Encerrando servidor...")
                running = False
                break
            elif cmd == "clients":
                with clients_lock:
                    for addr, c in clients.items():
                        print(f"{addr} -> {c}")
            elif cmd == "scores":
                print("Placar:", player_scores)
            else:
                print("Comando desconhecido. Use 'quit', 'clients' ou 'scores'.")
    except KeyboardInterrupt:
        print("KeyboardInterrupt: encerrando.")
        running = False

    time.sleep(1.0)
    servidor.close()
    print("Servidor finalizado.")
