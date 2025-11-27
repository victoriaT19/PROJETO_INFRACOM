import socket
import time
import os
import random

#ARQUIVO_RECEBIDO = "arquivo_recebido.bin"

#Configurações RDT 3.0
TIMEOUT = 2.0 
PROB_PERDA = 0.2 
ACK0 = b'ACK0'
ACK1 = b'ACK1'
BUFFER_SIZE = 1024 

##Funções Auxiliares RDT 3.0 
def make_pkt(seq_num, data):
    """Cria um pacote RDT com cabeçalho de número de sequência."""
    return str(seq_num).encode() + b'|' + data

def extract_pkt(packet):
    """Extrai o número de sequência e os dados de um pacote RDT."""
    separator_index = packet.find(b'|')
    if separator_index == -1: return -1, packet
    try:
        seq_num = int(packet[:separator_index].decode())
        data = packet[separator_index + 1:]
        return seq_num, data
    except ValueError:
        return -2, packet 

def make_ack(seq_num):
    """Cria uma mensagem ACK para o número de sequência especificado."""
    return (ACK0 if seq_num == 0 else ACK1)

def simulate_loss():
    """Simula a perda de um pacote com base na PROB_PERDA."""
    return random.random() < PROB_PERDA

##Cria um objeto socket para o servidor UDP
servidor = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
servidor.bind(("0.0.0.0", 5000))##Bind o socket a todas as interfaces de rede na porta 5000

print("Aguardando nome do arquivo...")

##Recebe o nome(extensão) do arquivo do cliente
nome_arquivo_bytes, endereco_cliente = servidor.recvfrom(1024)
nome_arquivo = nome_arquivo_bytes.decode()

###Recebe o tamanho do arquivo esperado do cliente
print("Aguardando tamanho do arquivo...")
tamanho_bytes, endereco_cliente = servidor.recvfrom(1024)
tamanho_esperado = int(tamanho_bytes.decode())
print(f"Nome '{nome_arquivo}', Tamanho: {tamanho_esperado} bytes.")

##Define o caminho onde o arquivo recebido será salvo
ARQUIVO_RECEBIDO = os.path.join("armazenamento_server",f"recebido_{nome_arquivo}")

print("Servidor UDP aguardando conexões na porta 5000...")

total_bytes = 0
expected_seq_num_recv = 0

with open(ARQUIVO_RECEBIDO, "wb") as arquivo_recebido:
    ##Loop para receber os pacotes do cliente até que o tamanho esperado seja alcançado
    while total_bytes < tamanho_esperado:
        try:
            ##Recebe pacotes de até 1024 bytes do cliente
            pacote, endereco_cliente = servidor.recvfrom(1024 + 5) # +5 para cabeçalho RDT
            
            seq_num_recebido, dados = extract_pkt(pacote)
            if seq_num_recebido == expected_seq_num_recv:
                print(f"  [RECEPTOR] Recebido pacote **{seq_num_recebido}** (esperado).")

            ##Escreve os dados recebidos no arquivo
                arquivo_recebido.write(dados)
                total_bytes += len(dados) ##atualiza o total de bytes recebidos

                ack_para_enviar = make_ack(expected_seq_num_recv)
                if simulate_loss():
                    print(f"  [SIMULAÇÃO] ACK {expected_seq_num_recv} PERDIDO no envio.")
                else:
                    servidor.sendto(ack_para_enviar, endereco_cliente)
                    print(f"  [RECEPTOR] Enviado ACK **{expected_seq_num_recv}**.")
                
                expected_seq_num_recv = 1 - expected_seq_num_recv

            elif seq_num_recebido != -1:
                print(f"  [RECEPTOR] Recebido pacote {seq_num_recebido} (duplicado/fora de ordem). Rejeitado.")
                ack_para_reenviar = make_ack(1 - expected_seq_num_recv)
                if simulate_loss():
                    print(f"  [SIMULAÇÃO] ACK {1 - expected_seq_num_recv} (Duplicado) PERDIDO no envio.")
                else:
                    servidor.sendto(ack_para_reenviar, endereco_cliente)
                    print(f"  [RECEPTOR] Reenviado ACK **{1 - expected_seq_num_recv}** (confirmando o anterior).")
            
            print(f"Recebido pacote de {len(dados)} bytes de {endereco_cliente}.")
        
        except socket.timeout:
            continue
        except Exception as e:
            print(f"  [RECEPTOR] Erro inesperado: {e}")
            break
    print(f"Arquivo recebido salvo como {ARQUIVO_RECEBIDO} ({total_bytes} bytes).")


pacotes_enviados = 0 
total_enviado = 0
next_seq_num_send = 0

##Envia a confirmação do tamanho do arquivo de volta para o cliente
print(f"Enviando confirmação de tamanho ({total_bytes} bytes) de volta para o cliente...")
servidor.sendto(str(total_bytes).encode(), endereco_cliente)

##Envia o arquivo de volta para o cliente em pacotes de 1024 bytes
with open(ARQUIVO_RECEBIDO, "rb") as arquivo_retorno:
    ##Loop para ler o arquivo em pedaços de 1024 bytes e enviar cada pedaço ao cliente
    while True:
        ##Lê até 1024 bytes do arquivo
        dados = arquivo_retorno.read(1024)
        ##Se read() retornar bytes vazios, significa que chegou ao fim do arquivo e então sai do loop
        if not dados:
            break
        while True:
            pkt = make_pkt(next_seq_num_send, dados)

            if simulate_loss():
                print(f"  [SIMULAÇÃO] Pacote {next_seq_num_send} PERDIDO no envio.")
            else:
                servidor.sendto(pkt, endereco_cliente)
                print(f"  [REMETENTE] Enviado pacote **{next_seq_num_send}**.")

            try:
                ack_bytes, _ = servidor.recvfrom(1024)
                ack = ack_bytes.decode()

                if ack == f'ACK{next_seq_num_send}':
                    print(f"  [REMETENTE] ACK {next_seq_num_send} recebido. Pacote aceito.")
                    next_seq_num_send = 1 - next_seq_num_send
                    break
                else:
                    print(f"  [REMETENTE] ACK duplicado/errado ({ack}) recebido. Reenviando...")
            
            except socket.timeout:
                print(f"  [REMETENTE] Timeout para pacote {next_seq_num_send}. **Reenviando**...")
                continue
        pacotes_enviados += 1 ##atualiza contadores
        total_enviado += len(dados)

print(f"Enviando {pacotes_enviados} pacotes ({total_enviado} bytes) de volta para o cliente...")
print("Envio de confirmação concluído.")

#Fecha o socket do servidor
servidor.close()