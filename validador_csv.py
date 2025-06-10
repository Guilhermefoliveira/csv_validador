import csv
import re
import os
import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback 
from copy import deepcopy

# --- Constantes e Configurações ---
EXPECTED_HEADER = ["NOME","EMPRESA","CPF","CEP","ENDERECO","NUMERO","COMPLEMENTO","BAIRRO","CIDADE","UF","AOS_CUIDADOS","NOTA_FISCAL","SERVICO","SERV_ADICIONAIS","VALOR_DECLARADO","OBSERVAÇÕES","CONTEUDO","DDD","TELEFONE","EMAIL","CHAVE","PESO","ALTURA","LARGURA","COMPRIMENTO","ENTREGA_VIZINHO","RFID"]
COLUNAS_OBRIGATORIAS = {"NOME", "CEP", "ENDERECO", "NUMERO", "BAIRRO", "CIDADE", "UF"}
API_TIMEOUT = 15
MAX_CONCURRENT_REQUESTS = 2
REQUEST_HEADERS = {'User-Agent': 'Mozilla/5.0'}
REGEX_CEP = r"^\d{5}-\d{3}$"
REGEX_TELEFONE = r"^\d{10,11}$"
REGEX_CPF = r"^\d{3}\.\d{3}\.\d{3}-\d{2}$|^\d{11}$"
REGEX_CNPJ = r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$|^\d{14}$"
REGEX_EMAIL = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

# --- Funções de API e Parsers ---
def _parse_viacep(r): return {"logradouro":r.get("logradouro"),"bairro":r.get("bairro"),"cidade":r.get("localidade"),"uf":r.get("uf")}, None if not r.get("erro") else "CEP não encontrado"
def _parse_brasilapi(r): return {"logradouro":r.get("street"),"bairro":r.get("neighborhood"),"cidade":r.get("city"),"uf":r.get("state")}, None
def _parse_opencep(r): return {"logradouro":r.get("logradouro"),"bairro":r.get("bairro"),"cidade":r.get("localidade"),"uf":r.get("uf")}, None if not r.get("erro") else "CEP não encontrado"
def _parse_postmon(r): return {"logradouro":r.get("logradouro"),"bairro":r.get("bairro"),"cidade":r.get("cidade"),"uf":r.get("estado")}, None
def _parse_brasilaberto(r):
    result = r.get("result", {})
    return {"logradouro":result.get("street"),"bairro":result.get("district"),"cidade":result.get("city"),"uf":result.get("stateShortname")}, None

API_PROVIDERS = [
    {"name": "BrasilAPI", "url": "https://brasilapi.com.br/api/cep/v1/{}", "parser": _parse_brasilapi},
    {"name": "OpenCEP", "url": "https://opencep.com/v1/{}", "parser": _parse_opencep},
    {"name": "Postmon", "url": "https://api.postmon.com.br/v1/cep/{}", "parser": _parse_postmon},
    {"name": "BrasilAberto", "url": "https://api.brasilaberto.com/v1/zipcode/{}", "parser": _parse_brasilaberto},
    {"name": "ViaCEP", "url": "https://viacep.com.br/ws/{}/json/", "parser": _parse_viacep},
]

def consultar_apis_cep(session, cep_numeros):
    if not str(cep_numeros).isdigit() or len(cep_numeros) != 8:
        return None, "Formato de CEP inválido para API."
    errors = []
    for provider in API_PROVIDERS:
        try:
            response = session.get(provider["url"].format(cep_numeros), timeout=API_TIMEOUT, headers=REQUEST_HEADERS)
            response.raise_for_status()
            data, err = provider["parser"](response.json())
            if err:
                errors.append(f"({provider['name']}: {err})")
                continue
            return data, None
        except requests.exceptions.RequestException as e:
            errors.append(f"({provider['name']}: {e})")
            continue
    return None, f"Falha em todas as APIs. Detalhes: {' | '.join(errors)}"

# --- Funções de Validação e Correção ---
def tentar_corrigir_cep(v):
    d = re.sub(r'\D', '', str(v))
    d = d.zfill(8) if 1 <= len(d) < 8 else d
    return f"{d[:5]}-{d[5:]}" if len(d) == 8 else v

def tentar_corrigir_cpf_cnpj(v):
    d = re.sub(r'\D', '', str(v))
    if len(d) == 11: return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d) == 14: return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return v

def corrigir_telefone(v): return re.sub(r'\D', '', str(v))

VALIDATION_RULES = {
    "NOME": {"validacao": (lambda v: len(v) <= 100), "msg": "Excede 100 caracteres."},
    "CEP": {"correcao": tentar_corrigir_cep, "validacao": (lambda v: re.match(REGEX_CEP, v)), "msg": "Formato inválido. Use NNNNN-NNN."},
    "TELEFONE": {"correcao": corrigir_telefone, "validacao": (lambda v: re.match(REGEX_TELEFONE, v)), "msg": "Deve ter 10 ou 11 dígitos."},
    "CPF": {"correcao": tentar_corrigir_cpf_cnpj, "validacao": (lambda v: re.match(REGEX_CPF, v) or re.match(REGEX_CNPJ, v)), "msg": "Formato de CPF/CNPJ inválido."},
    "EMAIL": {"validacao": (lambda v: re.match(REGEX_EMAIL, v)), "msg": "Formato de e-mail inválido."},
}

# --- Funções de Leitura e Escrita ---
def detectar_delimitador_e_encoding(caminho_arquivo):
    for encoding in ['utf-8-sig', 'latin-1', 'cp1252']:
        try:
            with open(caminho_arquivo, 'r', encoding=encoding, newline='') as f:
                sample = f.read(4096)
                if not sample: return None, None, None, "Arquivo está vazio."
                f.seek(0)
                delimiter = csv.Sniffer().sniff(sample, delimiters=';,').delimiter
                header = next(csv.reader(f, delimiter=delimiter))
                return header, delimiter, encoding, f"Lido com encoding '{encoding}' e delimitador '{delimiter}'."
        except Exception: continue
    return None, None, None, "Não foi possível decodificar ou determinar o formato do arquivo."

def salvar_csv_processado(caminho_arquivo_saida, dados_para_salvar):
    try:
        with open(caminho_arquivo_saida, mode='w', newline='', encoding='utf-8') as f:
            escritor = csv.writer(f, delimiter=';', quoting=csv.QUOTE_MINIMAL)
            for linha in dados_para_salvar:
                linha_limpa = [re.sub(r'\s+', ' ', str(campo)).strip() for campo in linha]
                escritor.writerow(linha_limpa)
        return True, f"Arquivo salvo com sucesso em: {caminho_arquivo_saida}"
    except IOError as e: return False, f"Erro de E/S ao salvar o arquivo: {e}"
    except Exception as e: return False, f"Erro inesperado ao salvar o arquivo: {e}\n{traceback.format_exc()}"


# --- Estrutura Principal de Validação ---
def validar_csv(caminho_arquivo, header_map=None, usar_api=True):
    cabecalho_original, delimitador, encoding, msg = detectar_delimitador_e_encoding(caminho_arquivo)
    if not cabecalho_original:
        return [msg or "Erro desconhecido"], [], [], [], [], []

    avisos = [msg] if msg else []
    with open(caminho_arquivo, 'r', encoding=encoding, newline='') as f:
        linhas_originais = list(csv.DictReader(f, delimiter=delimitador))

    cep_cache = {}
    if usar_api:
        coluna_cep_arquivo = next((k for k, v in (header_map or {}).items() if v == "CEP"), "CEP")
        if coluna_cep_arquivo in cabecalho_original:
            ceps_para_consulta = {str(linha.get(coluna_cep_arquivo, '')).strip() for linha in linhas_originais}
            ceps_validos = {re.sub(r'\D', '', cep).zfill(8) for cep in ceps_para_consulta if len(re.sub(r'\D', '', cep)) >= 7}
            if ceps_validos:
                with requests.Session() as session:
                    with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
                        future_to_cep = {executor.submit(consultar_apis_cep, session, cep): cep for cep in ceps_validos}
                        for future in as_completed(future_to_cep):
                            cep_cache[future_to_cep[future]] = future.result()
        else:
            avisos.append(f"Coluna de CEP ('{coluna_cep_arquivo}') não encontrada. Validação por API ignorada.")

    erros_totais, correcoes_totais = [], []
    dados_apenas_formato, dados_com_api = [cabecalho_original], [cabecalho_original]

    for i, linha_dict in enumerate(linhas_originais, start=2):
        if not any(linha_dict.values()): continue
        
        # 1. Mapeia para o formato do sistema
        valores_proc = {}
        mapa_auto = {h.upper(): h for h in EXPECTED_HEADER}
        for col_orig, val in linha_dict.items():
            col_sistema = (header_map or {}).get(col_orig, mapa_auto.get(col_orig.upper()))
            if col_sistema:
                valores_proc[col_sistema] = val.strip()
        
        # Cria cópias para os diferentes tipos de correção
        valores_com_formato_apenas = deepcopy(valores_proc)
        
        # 2. Aplica correções de formato
        for col, regra in VALIDATION_RULES.items():
            if "correcao" in regra and col in valores_com_formato_apenas:
                valores_com_formato_apenas[col] = regra["correcao"](valores_com_formato_apenas[col])
        
        # Começa a versão "completa" com as correções de formato já aplicadas
        valores_com_tudo = deepcopy(valores_com_formato_apenas)

        # 3. Aplica correções da API na versão "completa"
        if usar_api:
            cep_num = re.sub(r'\D', '', valores_com_tudo.get("CEP", ""))
            if cep_num in cep_cache:
                dados_api, erro_api = cep_cache[cep_num]
                if erro_api: avisos.append(f"Linha {i}, CEP {valores_com_tudo['CEP']}: {erro_api}")
                elif dados_api:
                    mapa_api = {"logradouro":"ENDERECO", "bairro":"BAIRRO", "cidade":"CIDADE", "uf":"UF"}
                    for api_key, csv_key in mapa_api.items():
                        v_api = dados_api.get(api_key,"").strip()
                        if v_api and v_api.upper() != valores_com_tudo.get(csv_key, "").upper():
                            valores_com_tudo[csv_key] = v_api
        
        # 4. Compara o original com o totalmente corrigido para gerar a lista de sugestões
        for col in valores_com_tudo:
            if valores_proc.get(col) != valores_com_tudo[col]:
                fonte = "API" if col in ["ENDERECO", "BAIRRO", "CIDADE", "UF"] and usar_api else "Formato"
                correcoes_totais.append({"linha": i, "coluna": col, "original": valores_proc.get(col), "corrigido": valores_com_tudo[col], "fonte": fonte})
        
        # 5. Valida a versão totalmente corrigida
        for col, val in valores_com_tudo.items():
            if col in COLUNAS_OBRIGATORIAS and not val:
                erros_totais.append({"linha": i, "coluna": col, "mensagem": "Campo obrigatório está vazio."})
            elif val and col in VALIDATION_RULES:
                regra = VALIDATION_RULES[col]
                if "validacao" in regra and not regra["validacao"](val):
                    erros_totais.append({"linha": i, "coluna": col, "mensagem": regra.get("msg", "Inválido")})

        # 6. Monta as duas linhas de saída
        linha_final_formato, linha_final_api = [], []
        for nome_col_original in cabecalho_original:
            coluna_sistema = (header_map or {h.upper():h for h in EXPECTED_HEADER}).get(nome_col_original.upper(), nome_col_original)
            
            if coluna_sistema in EXPECTED_HEADER:
                linha_final_formato.append(valores_com_formato_apenas.get(coluna_sistema, ""))
                linha_final_api.append(valores_com_tudo.get(coluna_sistema, ""))
            else:
                original_val = linha_dict.get(nome_col_original, "")
                linha_final_formato.append(original_val)
                linha_final_api.append(original_val)
        
        dados_apenas_formato.append(linha_final_formato)
        dados_com_api.append(linha_final_api)
        
    return [], sorted(list(set(avisos))), erros_totais, correcoes_totais, dados_apenas_formato, dados_com_api
