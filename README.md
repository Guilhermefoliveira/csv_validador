# Validador e Corretor de Arquivos CSV - PortalPostal

[https://imgur.com/WGhiblj](https://imgur.com/WGhiblj)

Uma aplicação de desktop robusta, desenvolvida em Python com PyQt6, para validar, corrigir e padronizar arquivos CSV de postagem. A ferramenta foi projetada para otimizar o fluxo de trabalho, garantindo a integridade dos dados antes da importação na plataforma web Portal Postal.

---

## ✨ Funcionalidades Principais

* **Validação Abrangente**: Verifica erros de formato, campos obrigatórios, e a estrutura geral do arquivo CSV.
* **Correção Inteligente de Dados**:
    * **Formato**: Corrige automaticamente o formato de CEPs, CPFs/CNPJs e telefones.
    * **Endereços (Opcional)**: Consulta 5 APIs públicas de CEP em sequência para validar e corrigir endereços, bairros, cidades e UFs, aumentando a precisão das entregas.
* **Flexibilidade de Entrada**:
    * **Detecção Automática**: Identifica automaticamente o delimitador (`;`) e o encoding do arquivo (`UTF-8`, `latin-1`, etc.).
    * **Mapeamento de Colunas**: Permite que o usuário mapeie manualmente as colunas do seu arquivo para os campos padrão do sistema através de uma interface intuitiva.
* **Controle Total do Usuário**:
    * **Validação Seletiva**: Oferece a opção de executar uma validação rápida (apenas formato) ou uma validação completa com consulta às APIs.
    * **Aplicação de Correções Opcional**: Ao salvar, o usuário pode escolher se deseja aplicar as correções de endereço sugeridas pela API, mantendo total controle sobre os dados.
* **Interface Gráfica Intuitiva**:
    * **Relatórios Claros**: Exibe erros, avisos e correções em abas organizadas.
    * **Responsividade**: Graças ao uso de threads, a interface nunca trava, mesmo ao processar arquivos grandes com consultas de API.
* **Geração de Logs**: Cria um arquivo `app_log.txt` para registrar o fluxo da aplicação e facilitar a depuração de erros.

---

## 🛠️ Tecnologias Utilizadas

* **Linguagem**: Python 3
* **Interface Gráfica**: PyQt6
* **Requisições HTTP**: Requests
* **Processamento Concorrente**: `concurrent.futures`

---

## 🚀 Como Executar o Projeto

### Pré-requisitos

* Python 3.8 ou superior instalado.
* Git (opcional, para clonar o repositório).

### 1. Clone o Repositório

```bash
git clone [https://github.com/seu-usuario/seu-repositorio.git](https://github.com/seu-usuario/seu-repositorio.git)
cd seu-repositorio
```

2. Crie um Ambiente Virtual (Recomendado)
```
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

3. Instale as Dependências
Crie um arquivo chamado requirements.txt na raiz do seu projeto com o seguinte conteúdo:
```
PyQt6
requests
```
Em seguida, instale as dependências com o pip:
```
pip install -r requirements.txt
```

4. Execute a Aplicação
Com o ambiente virtual ativado, execute o script da interface gráfica:
```
python validador_gui.py
```

⚙️ Como Usar a Aplicação
Selecione o Arquivo: Clique em "Procurar..." para carregar o seu arquivo CSV.
Mapeie as Colunas (Opcional):
Se os nomes das colunas do seu arquivo forem diferentes do padrão, use os menus suspensos para associar suas colunas às colunas do sistema.
Escolha o Tipo de Validação: 
Marque ou desmarque a caixa "Consultar API de CEP..." conforme sua necessidade.
Valide: 
Clique em "Validar Arquivo Selecionado".
Analise os Resultados: 
Navegue pelas abas "Erros e Avisos" e "Correções Sugeridas".
Salve o Arquivo: 
Clique em "Salvar Arquivo...", escolha o local e, se aplicável, decida na caixa de diálogo se deseja aplicar as correções de endereço.

📦 Como Gerar o Executável (.exe)
Para distribuir a aplicação como um único arquivo executável para Windows, use o PyInstaller.

Instale o PyInstaller:
```
pip install pyinstaller
```

Gere o Executável:
Certifique-se de ter um arquivo de ícone (icone.ico) na pasta do projeto e execute o seguinte comando no terminal:
```
pyinstaller --onefile --windowed --name "ValidadorCSV_PortalPostal" --icon="icone.ico" validador_gui.py
```
O arquivo ValidadorCSV_PortalPostal.exe será criado dentro de uma nova pasta chamada dist.

🤝 Contribuições

Contribuições, issues e sugestões de melhorias são sempre bem-vindos! Sinta-se à vontade para abrir uma issue para discutir uma nova funcionalidade ou relatar um bug.



