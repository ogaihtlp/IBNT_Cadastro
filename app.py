from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
import os
import bcrypt
import json

app = Flask(__name__)
app.secret_key = 'chave_secreta'

# Definição dos caminhos dos arquivos
USERS_FILE = 'usuarios.csv'
MEMBERS_FILE = 'membros.csv'
PESSOAS_FILE = 'pessoas.csv'

def init_files():
    """Inicializa os arquivos de usuários e membros se não existirem"""
    # Cria arquivo de usuários se não existir
    if not os.path.exists(USERS_FILE):
        df = pd.DataFrame(columns=['usuario', 'senha'])
        df.to_csv(USERS_FILE, index=False)
        # Cria usuário admin padrão
        criar_usuario_padrao('admin', '123456')
        print("Arquivo de usuários criado com usuário padrão: admin / 123456")
    
    # Cria arquivo de membros se não existir
    if not os.path.exists(MEMBERS_FILE):
        df = pd.DataFrame(columns=['Nome', 'Nascimento', 'Sexo', 'Estado Civil', 'Rua', 'Número', 'Bairro',
                                   'Data do Batismo', 'Batismo em Outra Igreja', 'Nome da Igreja', 'Dependentes'])
        df.to_csv(MEMBERS_FILE, index=False)
        print("Arquivo de membros criado")

    if not os.path.exists(PESSOAS_FILE):
        df = pd.DataFrame(columns=['Nome', 'Nascimento', 'Sexo', 'Estado Civil', 'Rua', 'Número', 'Bairro',
                                  'Situação', 'Observações', 'Data de Cadastro', 'Dependentes'])
        df.to_csv(PESSOAS_FILE, index=False)
        print("Arquivo de pessoas criado")

def criar_usuario_padrao(usuario, senha):
    """Cria um usuário padrão com senha hashada"""
    # Gera hash da senha
    salt = bcrypt.gensalt()
    senha_hashada = bcrypt.hashpw(senha.encode('utf-8'), salt)
    
    # Adiciona ao arquivo
    df = pd.read_csv(USERS_FILE)
    novo_usuario = pd.DataFrame([[usuario, senha_hashada.decode('utf-8')]], 
                                columns=['usuario', 'senha'])
    df = pd.concat([df, novo_usuario], ignore_index=True)
    df.to_csv(USERS_FILE, index=False)

def criar_usuario(usuario, senha):
    """Cria um novo usuário"""
    # Verificar se usuário já existe
    df = pd.read_csv(USERS_FILE)
    if usuario in df['usuario'].values:
        return False
    
    # Gera hash da senha
    salt = bcrypt.gensalt()
    senha_hashada = bcrypt.hashpw(senha.encode('utf-8'), salt)
    
    # Adiciona ao arquivo
    novo_usuario = pd.DataFrame([[usuario, senha_hashada.decode('utf-8')]], 
                                columns=['usuario', 'senha'])
    df = pd.concat([df, novo_usuario], ignore_index=True)
    df.to_csv(USERS_FILE, index=False)
    return True

@app.route('/', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if request.method == 'POST':
        usuario = request.form['usuario']
        senha = request.form['senha'].encode('utf-8')
        
        # Verifica se arquivo existe
        if not os.path.exists(USERS_FILE):
            init_files()
        
        # Verifica credenciais
        df = pd.read_csv(USERS_FILE)
        
        # Verificar se as colunas existem
        if 'usuario' not in df.columns or 'senha' not in df.columns:
            print("Colunas não encontradas no arquivo de usuários. Recriando arquivo...")
            os.remove(USERS_FILE)  # Remove o arquivo corrompido
            init_files()  # Cria um novo arquivo com as colunas corretas
            df = pd.read_csv(USERS_FILE)  # Carrega o novo arquivo
        
        user = df[df['usuario'] == usuario]
        
        if not user.empty and bcrypt.checkpw(senha, user.iloc[0]['senha'].encode('utf-8')):
            session['usuario'] = usuario
            return redirect(url_for('dashboard'))
        
        flash('Usuário ou senha incorretos.', 'error')
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    """Dashboard principal"""
    if 'usuario' not in session:
        flash('Você precisa fazer login para acessar o dashboard.', 'error')
        return redirect(url_for('login'))
    
    # Inicializa os arquivos se não existirem
    if not os.path.exists(MEMBERS_FILE) or not os.path.exists(PESSOAS_FILE):
        init_files()
    
    # Carrega dados dos membros
    df_membros = pd.read_csv(MEMBERS_FILE)
    total_membros = len(df_membros)
    homens_membros = len(df_membros[df_membros['Sexo'] == 'Masculino'])
    mulheres_membros = len(df_membros[df_membros['Sexo'] == 'Feminino'])
    
    # Carrega dados das pessoas (não membros)
    df_pessoas = pd.read_csv(PESSOAS_FILE)
    total_pessoas = len(df_pessoas)
    visitantes = len(df_pessoas[df_pessoas['Situação'] == 'Visitante'])
    novos_convertidos = len(df_pessoas[df_pessoas['Situação'] == 'Novo Convertido'])
    
    # Contagem de dependentes (para ambos, membros e pessoas)
    total_dependentes = 0
    
    # Conta dependentes de membros
    for deps in df_membros['Dependentes']:
        if isinstance(deps, str) and deps.strip():
            try:
                deps_list = json.loads(deps)
                total_dependentes += len(deps_list)
            except:
                pass
    
    # Conta dependentes de pessoas não-membros
    for deps in df_pessoas['Dependentes']:
        if isinstance(deps, str) and deps.strip():
            try:
                deps_list = json.loads(deps)
                total_dependentes += len(deps_list)
            except:
                pass
    
    # Últimos cadastros (combinando membros e pessoas)
    ultimos_membros = []
    if not df_membros.empty:
        ultimos_membros = df_membros.tail(3).to_dict('records')
    
    ultimas_pessoas = []
    if not df_pessoas.empty:
        ultimas_pessoas = df_pessoas.tail(3).to_dict('records')
    
    return render_template('dashboard.html', 
                          total_membros=total_membros, 
                          homens_membros=homens_membros, 
                          mulheres_membros=mulheres_membros,
                          total_pessoas=total_pessoas,
                          visitantes=visitantes,
                          novos_convertidos=novos_convertidos,
                          total_dependentes=total_dependentes,
                          ultimos_membros=ultimos_membros,
                          ultimas_pessoas=ultimas_pessoas)

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    """Página de cadastro de membros"""
    if 'usuario' not in session:
        flash('Você precisa fazer login para acessar o cadastro.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        nome = request.form['nome']
        nascimento = request.form['nascimento']
        sexo = request.form['sexo']
        estado_civil = request.form['estado_civil']
        rua = request.form['rua']
        numero = request.form['numero']
        bairro = request.form['bairro']
        data_batismo = request.form.get('data_batismo', '')
        batismo_outra_igreja = request.form.get('batismo_outra_igreja', 'Não')
        nome_igreja = request.form.get('nome_igreja', '')
        
        # Processa dependentes
        dependentes = []
        dep_nomes = request.form.getlist('dep_nome')
        if dep_nomes:
            for i in range(len(dep_nomes)):
                if dep_nomes[i]:  # Verifica se o nome não está vazio
                    dependente = {
                        "Nome": dep_nomes[i],
                        "Nascimento": request.form.getlist('dep_nascimento')[i] if i < len(request.form.getlist('dep_nascimento')) else "",
                        "Batizado": request.form.getlist('dep_batizado')[i] if i < len(request.form.getlist('dep_batizado')) else "Não"
                    }
                    dependentes.append(dependente)
        
        # Salva o novo membro
        df = pd.read_csv(MEMBERS_FILE)
        novo_membro = pd.DataFrame([[nome, nascimento, sexo, estado_civil, rua, numero, bairro, 
                                     data_batismo, batismo_outra_igreja, nome_igreja, json.dumps(dependentes)]],
                                    columns=['Nome', 'Nascimento', 'Sexo', 'Estado Civil', 'Rua', 'Número', 'Bairro',
                                             'Data do Batismo', 'Batismo em Outra Igreja', 'Nome da Igreja', 'Dependentes'])
        df = pd.concat([df, novo_membro], ignore_index=True)
        df.to_csv(MEMBERS_FILE, index=False)
        
        flash('Membro cadastrado com sucesso!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('cadastro.html')

@app.route('/usuario', methods=['GET', 'POST'])
def gerenciar_usuario():
    """Página para gerenciar usuários"""
    if 'usuario' not in session:
        flash('Você precisa fazer login para gerenciar usuários.', 'error')
        return redirect(url_for('login'))
    
    # Apenas o admin pode gerenciar usuários
    if session['usuario'] != 'admin':
        flash('Apenas o administrador pode gerenciar usuários.', 'error')
        return redirect(url_for('dashboard'))
    
    # Lista de usuários existentes
    df = pd.read_csv(USERS_FILE)
    usuarios = df['usuario'].tolist()
    
    if request.method == 'POST':
        novo_usuario = request.form['novo_usuario']
        nova_senha = request.form['nova_senha']
        
        # Criação de novo usuário
        if criar_usuario(novo_usuario, nova_senha):
            flash(f'Usuário {novo_usuario} criado com sucesso!', 'success')
        else:
            flash(f'Usuário {novo_usuario} já existe!', 'error')
        
        return redirect(url_for('gerenciar_usuario'))
    
    return render_template('usuario.html', usuarios=usuarios)

@app.route('/logout')
def logout():
    """Encerra a sessão"""
    session.pop('usuario', None)
    flash('Você foi desconectado.', 'info')
    return redirect(url_for('login'))

@app.errorhandler(404)
def page_not_found(e):
    """Tratamento de erro 404"""
    flash('Página não encontrada!', 'error')
    if 'usuario' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/membros')
def listar_membros():
    """Página para visualizar todos os membros cadastrados"""
    if 'usuario' not in session:
        flash('Você precisa fazer login para acessar a lista de membros.', 'error')
        return redirect(url_for('login'))
    
    # Carrega dados dos membros
    if not os.path.exists(MEMBERS_FILE):
        init_files()
    
    df = pd.read_csv(MEMBERS_FILE)
    
    # Converte o DataFrame para uma lista de dicionários (melhor para o template)
    membros = df.to_dict('records')
    
    return render_template('membros.html', membros=membros)

@app.route('/membro/<int:indice>')
def visualizar_membro(indice):
    """Página para visualizar detalhes de um membro específico"""
    if 'usuario' not in session:
        flash('Você precisa fazer login para visualizar os detalhes.', 'error')
        return redirect(url_for('login'))
    
    df = pd.read_csv(MEMBERS_FILE)
    
    # Verifica se o índice existe
    if indice >= len(df):
        flash('Membro não encontrado.', 'error')
        return redirect(url_for('listar_membros'))
    
    # Obtém o membro
    membro = df.iloc[indice].to_dict()
    
    # Converte os dependentes de JSON para lista
    if isinstance(membro['Dependentes'], str):
        membro['Dependentes'] = json.loads(membro['Dependentes'])
    else:
        membro['Dependentes'] = []
    
    return render_template('visualizar_membro.html', membro=membro, indice=indice)

@app.route('/membro/editar/<int:indice>', methods=['GET', 'POST'])
def editar_membro(indice):
    """Página para editar um membro"""
    if 'usuario' not in session:
        flash('Você precisa fazer login para editar membros.', 'error')
        return redirect(url_for('login'))
    
    df = pd.read_csv(MEMBERS_FILE)
    
    # Verifica se o índice existe
    if indice >= len(df):
        flash('Membro não encontrado.', 'error')
        return redirect(url_for('listar_membros'))
    
    if request.method == 'POST':
        # Atualizando os dados no DataFrame
        nome = request.form['nome']
        nascimento = request.form['nascimento']
        sexo = request.form['sexo']
        estado_civil = request.form['estado_civil']
        rua = request.form['rua']
        numero = request.form['numero']
        bairro = request.form['bairro']
        data_batismo = request.form.get('data_batismo', '')
        batismo_outra_igreja = request.form.get('batismo_outra_igreja', 'Não')
        nome_igreja = request.form.get('nome_igreja', '')
        
        # Processa dependentes
        dependentes = []
        dep_nomes = request.form.getlist('dep_nome')
        if dep_nomes:
            for i in range(len(dep_nomes)):
                if dep_nomes[i]:  # Verifica se o nome não está vazio
                    dependente = {
                        "Nome": dep_nomes[i],
                        "Nascimento": request.form.getlist('dep_nascimento')[i] if i < len(request.form.getlist('dep_nascimento')) else "",
                        "Batizado": request.form.getlist('dep_batizado')[i] if i < len(request.form.getlist('dep_batizado')) else "Não"
                    }
                    dependentes.append(dependente)
        
        # Atualiza o DataFrame
        df.at[indice, 'Nome'] = nome
        df.at[indice, 'Nascimento'] = nascimento
        df.at[indice, 'Sexo'] = sexo
        df.at[indice, 'Estado Civil'] = estado_civil
        df.at[indice, 'Rua'] = rua
        df.at[indice, 'Número'] = numero
        df.at[indice, 'Bairro'] = bairro
        df.at[indice, 'Data do Batismo'] = data_batismo
        df.at[indice, 'Batismo em Outra Igreja'] = batismo_outra_igreja
        df.at[indice, 'Nome da Igreja'] = nome_igreja
        df.at[indice, 'Dependentes'] = json.dumps(dependentes)
        
        # Salva o DataFrame atualizado
        df.to_csv(MEMBERS_FILE, index=False)
        
        flash('Membro atualizado com sucesso!', 'success')
        return redirect(url_for('visualizar_membro', indice=indice))
    
    # Para requisição GET, busca os dados atuais para edição
    membro = df.iloc[indice].to_dict()
    
    # Converte os dependentes de JSON para lista
    if isinstance(membro['Dependentes'], str):
        membro['Dependentes'] = json.loads(membro['Dependentes'])
    else:
        membro['Dependentes'] = []
    
    return render_template('editar_membro.html', membro=membro, indice=indice)

@app.route('/membro/excluir/<int:indice>', methods=['POST'])
def excluir_membro(indice):
    """Rota para excluir um membro"""
    if 'usuario' not in session:
        flash('Você precisa fazer login para excluir membros.', 'error')
        return redirect(url_for('login'))
    
    df = pd.read_csv(MEMBERS_FILE)
    
    # Verifica se o índice existe
    if indice >= len(df):
        flash('Membro não encontrado.', 'error')
        return redirect(url_for('listar_membros'))
    
    # Remove a linha do DataFrame
    df = df.drop(indice).reset_index(drop=True)
    
    # Salva o DataFrame atualizado
    df.to_csv(MEMBERS_FILE, index=False)
    
    flash('Membro excluído com sucesso!', 'success')
    return redirect(url_for('listar_membros'))

def init_files():
    """Inicializa os arquivos de usuários, membros e pessoas se não existirem"""
    # Cria arquivo de usuários se não existir
    if not os.path.exists(USERS_FILE):
        df = pd.DataFrame(columns=['usuario', 'senha'])
        df.to_csv(USERS_FILE, index=False)
        # Cria usuário admin padrão
        criar_usuario_padrao('admin', '123456')
        print("Arquivo de usuários criado com usuário padrão: admin / 123456")
    
    # Cria arquivo de membros se não existir
    if not os.path.exists(MEMBERS_FILE):
        df = pd.DataFrame(columns=['Nome', 'Nascimento', 'Sexo', 'Estado Civil', 'Rua', 'Número', 'Bairro',
                                   'Data do Batismo', 'Batismo em Outra Igreja', 'Nome da Igreja', 'Dependentes'])
        df.to_csv(MEMBERS_FILE, index=False)
        print("Arquivo de membros criado")
    
    # Cria arquivo de pessoas se não existir
    if not os.path.exists(PESSOAS_FILE):
        df = pd.DataFrame(columns=['Nome', 'Nascimento', 'Sexo', 'Estado Civil', 'Rua', 'Número', 'Bairro',
                                  'Situação', 'Observações', 'Data de Cadastro', 'Dependentes'])
        df.to_csv(PESSOAS_FILE, index=False)
        print("Arquivo de pessoas criado")

# Adicione as rotas para gerenciar pessoas (não membros)
@app.route('/pessoas')
def listar_pessoas():
    """Página para visualizar todas as pessoas cadastradas (não membros)"""
    if 'usuario' not in session:
        flash('Você precisa fazer login para acessar a lista de pessoas.', 'error')
        return redirect(url_for('login'))
    
    # Carrega dados das pessoas
    if not os.path.exists(PESSOAS_FILE):
        init_files()
    
    df = pd.read_csv(PESSOAS_FILE)
    
    # Converte o DataFrame para uma lista de dicionários
    pessoas = df.to_dict('records')
    
    return render_template('pessoas.html', pessoas=pessoas)

@app.route('/pessoa/cadastro', methods=['GET', 'POST'])
def cadastro_pessoa():
    """Página de cadastro de pessoas (não membros)"""
    if 'usuario' not in session:
        flash('Você precisa fazer login para acessar o cadastro.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        nome = request.form['nome']
        nascimento = request.form['nascimento']
        sexo = request.form['sexo']
        estado_civil = request.form['estado_civil']
        rua = request.form['rua']
        numero = request.form['numero']
        bairro = request.form['bairro']
        situacao = request.form['situacao']
        observacoes = request.form.get('observacoes', '')
        
        # Obter a data atual para o campo 'Data de Cadastro'
        from datetime import date
        data_cadastro = date.today().strftime('%Y-%m-%d')
        
        # Processa dependentes
        dependentes = []
        dep_nomes = request.form.getlist('dep_nome')
        if dep_nomes:
            for i in range(len(dep_nomes)):
                if dep_nomes[i]:  # Verifica se o nome não está vazio
                    dependente = {
                        "Nome": dep_nomes[i],
                        "Nascimento": request.form.getlist('dep_nascimento')[i] if i < len(request.form.getlist('dep_nascimento')) else "",
                        "Batizado": request.form.getlist('dep_batizado')[i] if i < len(request.form.getlist('dep_batizado')) else "Não"
                    }
                    dependentes.append(dependente)
        
        # Se a situação for 'Membro', transferir para o cadastro de membros
        if situacao == 'Membro':
            # Preparar dados para adicionar ao arquivo de membros
            df_membros = pd.read_csv(MEMBERS_FILE)
            novo_membro = pd.DataFrame([[nome, nascimento, sexo, estado_civil, rua, numero, bairro, 
                                        '', 'Não', '', json.dumps(dependentes)]],
                                       columns=['Nome', 'Nascimento', 'Sexo', 'Estado Civil', 'Rua', 'Número', 'Bairro',
                                               'Data do Batismo', 'Batismo em Outra Igreja', 'Nome da Igreja', 'Dependentes'])
            df_membros = pd.concat([df_membros, novo_membro], ignore_index=True)
            df_membros.to_csv(MEMBERS_FILE, index=False)
            
            flash('Pessoa cadastrada como membro com sucesso!', 'success')
            return redirect(url_for('listar_membros'))
        else:
            # Salva a nova pessoa no arquivo de pessoas
            df = pd.read_csv(PESSOAS_FILE)
            nova_pessoa = pd.DataFrame([[nome, nascimento, sexo, estado_civil, rua, numero, bairro, 
                                        situacao, observacoes, data_cadastro, json.dumps(dependentes)]],
                                      columns=['Nome', 'Nascimento', 'Sexo', 'Estado Civil', 'Rua', 'Número', 'Bairro',
                                              'Situação', 'Observações', 'Data de Cadastro', 'Dependentes'])
            df = pd.concat([df, nova_pessoa], ignore_index=True)
            df.to_csv(PESSOAS_FILE, index=False)
            
            flash('Pessoa cadastrada com sucesso!', 'success')
            return redirect(url_for('listar_pessoas'))
    
    return render_template('cadastro_pessoa.html')

@app.route('/pessoa/<int:indice>')
def visualizar_pessoa(indice):
    """Página para visualizar detalhes de uma pessoa específica"""
    if 'usuario' not in session:
        flash('Você precisa fazer login para visualizar os detalhes.', 'error')
        return redirect(url_for('login'))
    
    df = pd.read_csv(PESSOAS_FILE)
    
    # Verifica se o índice existe
    if indice >= len(df):
        flash('Pessoa não encontrada.', 'error')
        return redirect(url_for('listar_pessoas'))
    
    # Obtém a pessoa
    pessoa = df.iloc[indice].to_dict()
    
    # Converte os dependentes de JSON para lista
    if isinstance(pessoa['Dependentes'], str):
        pessoa['Dependentes'] = json.loads(pessoa['Dependentes'])
    else:
        pessoa['Dependentes'] = []
    
    return render_template('visualizar_pessoa.html', pessoa=pessoa, indice=indice)

@app.route('/pessoa/editar/<int:indice>', methods=['GET', 'POST'])
def editar_pessoa(indice):
    """Página para editar uma pessoa"""
    if 'usuario' not in session:
        flash('Você precisa fazer login para editar pessoas.', 'error')
        return redirect(url_for('login'))
    
    df = pd.read_csv(PESSOAS_FILE)
    
    # Verifica se o índice existe
    if indice >= len(df):
        flash('Pessoa não encontrada.', 'error')
        return redirect(url_for('listar_pessoas'))
    
    if request.method == 'POST':
        # Atualizando os dados no DataFrame
        nome = request.form['nome']
        nascimento = request.form['nascimento']
        sexo = request.form['sexo']
        estado_civil = request.form['estado_civil']
        rua = request.form['rua']
        numero = request.form['numero']
        bairro = request.form['bairro']
        situacao = request.form['situacao']
        observacoes = request.form.get('observacoes', '')
        
        # Processa dependentes
        dependentes = []
        dep_nomes = request.form.getlist('dep_nome')
        if dep_nomes:
            for i in range(len(dep_nomes)):
                if dep_nomes[i]:  # Verifica se o nome não está vazio
                    dependente = {
                        "Nome": dep_nomes[i],
                        "Nascimento": request.form.getlist('dep_nascimento')[i] if i < len(request.form.getlist('dep_nascimento')) else "",
                        "Batizado": request.form.getlist('dep_batizado')[i] if i < len(request.form.getlist('dep_batizado')) else "Não"
                    }
                    dependentes.append(dependente)
        
        # Se a situação foi alterada para 'Membro', transferir para o cadastro de membros
        situacao_antiga = df.at[indice, 'Situação']
        
        if situacao == 'Membro' and situacao_antiga != 'Membro':
            # Adicionar ao arquivo de membros
            df_membros = pd.read_csv(MEMBERS_FILE)
            novo_membro = pd.DataFrame([[nome, nascimento, sexo, estado_civil, rua, numero, bairro, 
                                        '', 'Não', '', json.dumps(dependentes)]],
                                       columns=['Nome', 'Nascimento', 'Sexo', 'Estado Civil', 'Rua', 'Número', 'Bairro',
                                               'Data do Batismo', 'Batismo em Outra Igreja', 'Nome da Igreja', 'Dependentes'])
            df_membros = pd.concat([df_membros, novo_membro], ignore_index=True)
            df_membros.to_csv(MEMBERS_FILE, index=False)
            
            # Remover do arquivo de pessoas
            df = df.drop(indice).reset_index(drop=True)
            df.to_csv(PESSOAS_FILE, index=False)
            
            flash('Pessoa promovida a membro com sucesso!', 'success')
            return redirect(url_for('listar_membros'))
        else:
            # Atualiza o DataFrame de pessoas
            df.at[indice, 'Nome'] = nome
            df.at[indice, 'Nascimento'] = nascimento
            df.at[indice, 'Sexo'] = sexo
            df.at[indice, 'Estado Civil'] = estado_civil
            df.at[indice, 'Rua'] = rua
            df.at[indice, 'Número'] = numero
            df.at[indice, 'Bairro'] = bairro
            df.at[indice, 'Situação'] = situacao
            df.at[indice, 'Observações'] = observacoes
            df.at[indice, 'Dependentes'] = json.dumps(dependentes)
            
            # Salva o DataFrame atualizado
            df.to_csv(PESSOAS_FILE, index=False)
            
            flash('Pessoa atualizada com sucesso!', 'success')
            return redirect(url_for('visualizar_pessoa', indice=indice))
    
    # Para requisição GET, busca os dados atuais para edição
    pessoa = df.iloc[indice].to_dict()
    
    # Converte os dependentes de JSON para lista
    if isinstance(pessoa['Dependentes'], str):
        pessoa['Dependentes'] = json.loads(pessoa['Dependentes'])
    else:
        pessoa['Dependentes'] = []
    
    return render_template('editar_pessoa.html', pessoa=pessoa, indice=indice)

@app.route('/pessoa/excluir/<int:indice>', methods=['POST'])
def excluir_pessoa(indice):
    """Rota para excluir uma pessoa"""
    if 'usuario' not in session:
        flash('Você precisa fazer login para excluir pessoas.', 'error')
        return redirect(url_for('login'))
    
    df = pd.read_csv(PESSOAS_FILE)
    
    # Verifica se o índice existe
    if indice >= len(df):
        flash('Pessoa não encontrada.', 'error')
        return redirect(url_for('listar_pessoas'))
    
    # Remove a linha do DataFrame
    df = df.drop(indice).reset_index(drop=True)
    
    # Salva o DataFrame atualizado
    df.to_csv(PESSOAS_FILE, index=False)
    
    flash('Pessoa excluída com sucesso!', 'success')
    return redirect(url_for('listar_pessoas'))

if __name__ == '__main__':
    # Inicializa os arquivos ao iniciar o aplicativo
    init_files()
    app.run(debug=True)