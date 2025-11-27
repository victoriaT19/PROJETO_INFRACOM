import socket
import time
import os
import random

##Configurações RDT 3.0
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

caminho_arquivo = "mapa_westeros.jpg" ## caminho do arquivo que vai ser enviado, deve estar na pasta UDP

#Define o caminho onde o arquivo de retorno será salvo
#O nome do arquivo de retorno será "devolvido_" + nome do arquivo original e sera salvo na pasta "armazenamento_cliente"
ARQUIVO_FINAL = os.path.join("armazenamento_cliente", "devolvido_" + os.path.basename(caminho_arquivo))

#Cria um objeto socket para o cliente
cliente = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
end_servidor =  ("127.0.0.1", 5000) #Define o endereço (IP e porta) do servidor para onde os dados serão enviados."127.0.0.1" é o localhost, que é a própria máquina

#Envia o nome/extensão do arquivo para o servidor
print("Enviando nome/extensão do arquivo para o servidor...")
cliente.sendto(caminho_arquivo.encode(), end_servidor)

#Obtém o tamanho do arquivo a ser enviado
tamanho_arquivo = os.path.getsize(caminho_arquivo)
print(f"Enviando tamanho do arquivo: {tamanho_arquivo} bytes")
cliente.sendto(str(tamanho_arquivo).encode(), end_servidor)

print(f"Enviando arquivo em pacotes de 1024 bytes para o servidor...")

pacotes_enviados = 0
total_enviado = 0
next_seq_num_send = 0

with open(caminho_arquivo, "rb") as arquivo:
    ##Loop para ler o arquivo em pedaços de 1024 bytes e enviar cada pedaço ao servidor
    while True:
        #Lê até 1024 bytes do arquivo
        dados = arquivo.read(1024)
        #Se read() retornar bytes vazios, significa que chegou ao fim do arquivo e então sai do loop
        if not dados:
            break
        while True:
            pkt = make_pkt(next_seq_num_send, dados)

            if simulate_loss():
                print(f"  [SIMULAÇÃO] Pacote {next_seq_num_send} PERDIDO no envio.")
            else:
                cliente.sendto(pkt, end_servidor)
                print(f"  [REMETENTE] Enviado pacote **{next_seq_num_send}**.")

            try:
                ack_bytes, _ = cliente.recvfrom(1024)
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
        pacotes_enviados += 1 #contadores
        total_enviado += len(dados)
        time.sleep(0.001) ## adicionado um delayzinho para evitar perda de pacotes, devido a rapidez do envio
print(f"Envio concluído ({pacotes_enviados} pacotes, {total_enviado} bytes). Aguardando confirmação do servidor...")

total_recebido = 0
pacotes_recebidos = 0
expected_seq_num_recv = 0

print("Aguardando confirmação de tamanho do servidor...")
tamanho_retorno_bytes, _ = cliente.recvfrom(1024)
tamanho_retorno_esperado = int(tamanho_retorno_bytes.decode())
print(f"Servidor confirmou. Recebendo mensagem de {tamanho_retorno_esperado} bytes...")

with open(ARQUIVO_FINAL, "wb") as arquivo_recebido:
    ##Loop para receber os pacotes de volta do servidor
    while total_recebido < tamanho_retorno_esperado:
        try:
            ##Recebe pacotes de até 1024 bytes do servido
            pacotes_retorno, _ = cliente.recvfrom(1024 + 5)
            
            seq_num_recebido, dados = extract_pkt(pacotes_retorno)

            if seq_num_recebido == expected_seq_num_recv:
                print(f"  [RECEPTOR] Recebido pacote **{seq_num_recebido}** (esperado).")

                ##Escreve os dados recebidos no arquivo de retorno
                arquivo_recebido.write(dados)
                total_recebido += len(dados) ##Contadores
                pacotes_recebidos += 1

                ack_para_enviar = make_ack(expected_seq_num_recv)
                if simulate_loss():
                    print(f"  [SIMULAÇÃO] ACK {expected_seq_num_recv} PERDIDO no envio.")
                else:
                    cliente.sendto(ack_para_enviar, end_servidor)
                    print(f"  [RECEPTOR] Enviado ACK **{expected_seq_num_recv}**.")
                
                expected_seq_num_recv = 1 - expected_seq_num_recv

            elif seq_num_recebido != -1:
                print(f"  [RECEPTOR] Recebido pacote {seq_num_recebido} (duplicado/fora de ordem). Rejeitado.")
                ack_para_reenviar = make_ack(1 - expected_seq_num_recv)
                if simulate_loss():
                    print(f"  [SIMULAÇÃO] ACK {1 - expected_seq_num_recv} (Duplicado) PERDIDO no envio.")
                else:
                    cliente.sendto(ack_para_reenviar, end_servidor)
                    print(f"  [RECEPTOR] Reenviado ACK **{1 - expected_seq_num_recv}** (confirmando o anterior).")
        
        except socket.timeout:
            continue
        except Exception as e:
            print(f"  [RECEPTOR] Erro inesperado: {e}")
            break   
print(f"Arquivo recebido salvo como {ARQUIVO_FINAL} ({total_recebido} bytes em {pacotes_recebidos} pacotes)." )

#Fecha o socket do cliente
cliente.close()