from flask import Flask, render_template, request, redirect, url_for, session, flash
import pandas as pd
import os
import bcrypt
import json
from datetime import date, datetime

app = Flask(__name__)
app.secret_key = 'chave_secreta'

# Definição dos caminhos dos arquivos
USERS_FILE = 'usuarios.csv'
MEMBERS_FILE = 'membros.csv'
PESSOAS_FILE = 'pessoas.csv'

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
                                   'Data do Batismo', 'Batismo em Outra Igreja', 'Nome da Igreja', 'Dependentes',
                                   'É Dependente', 'ID Responsável'])
        df.to_csv(MEMBERS_FILE, index=False)
        print("Arquivo de membros criado")

    if not os.path.exists(PESSOAS_FILE):
        df = pd.DataFrame(columns=['Nome', 'Nascimento', 'Sexo', 'Estado Civil', 'Rua', 'Número', 'Bairro',
                                  'Situação', 'Observações', 'Data de Cadastro', 'Dependentes',
                                  'É Dependente', 'ID Responsável'])
        df.to_csv(PESSOAS_FILE, index=False)
        print("Arquivo de pessoas criado")

def migrar_dados_existentes():
    """Migra dados existentes para o novo formato com colunas adicionais"""
    # Migrar membros
    if os.path.exists(MEMBERS_FILE):
        df = pd.read_csv(MEMBERS_FILE)
        if 'É Dependente' not in df.columns:
            df['É Dependente'] = 'Não'
        if 'ID Responsável' not in df.columns:
            df['ID Responsável'] = ''
        df.to_csv(MEMBERS_FILE, index=False)
    
    # Migrar pessoas
    if os.path.exists(PESSOAS_FILE):
        df = pd.read_csv(PESSOAS_FILE)
        if 'É Dependente' not in df.columns:
            df['É Dependente'] = 'Não'
        if 'ID Responsável' not in df.columns:
            df['ID Responsável'] = ''
        df.to_csv(PESSOAS_FILE, index=False)

def corrigir_dependentes_membros():
    """NOVA FUNÇÃO: Corrige registros de dependentes-membros que foram salvos incorretamente"""
    df_membros = pd.read_csv(MEMBERS_FILE)
    
    for index, membro in df_membros.iterrows():
        if isinstance(membro['Dependentes'], str) and membro['Dependentes'].strip():
            try:
                dependentes = json.loads(membro['Dependentes'])
                dependentes_atualizados = []
                
                for dep in dependentes:
                    # Procurar dependentes que deveriam ser membros mas estão como simples
                    if dep.get('tipo', 'simples') == 'simples':
                        # Verificar se existe um membro com o mesmo nome que deveria ser dependente-membro
                        nome_dep = dep.get('Nome', '')
                        nascimento_dep = dep.get('Nascimento', '')
                        
                        # Procurar membro correspondente
                        membro_correspondente = df_membros[
                            (df_membros['Nome'] == nome_dep) & 
                            (df_membros['Nascimento'] == nascimento_dep) &
                            (df_membros.index != index)  # Não incluir o próprio membro
                        ]
                        
                        if not membro_correspondente.empty:
                            # Encontrou membro correspondente - atualizar para dependente-membro
                            id_membro = membro_correspondente.index[0]
                            
                            # Atualizar o membro para ser dependente
                            df_membros.at[id_membro, 'É Dependente'] = 'Sim'
                            df_membros.at[id_membro, 'ID Responsável'] = str(index)
                            
                            # Atualizar na lista de dependentes
                            dep_atualizado = {
                                "tipo": "membro",
                                "Nome": nome_dep,
                                "ID_Membro": id_membro
                            }
                            dependentes_atualizados.append(dep_atualizado)
                            print(f"Corrigido: {nome_dep} agora é dependente-membro de {membro['Nome']}")
                        else:
                            # Manter como dependente simples
                            dependentes_atualizados.append(dep)
                    else:
                        # Já é dependente-membro, manter
                        dependentes_atualizados.append(dep)
                
                # Atualizar a lista de dependentes do membro responsável
                df_membros.at[index, 'Dependentes'] = json.dumps(dependentes_atualizados)
                
            except Exception as e:
                print(f"Erro ao processar dependentes do membro {membro['Nome']}: {e}")
                continue
    
    # Salvar as correções
    df_membros.to_csv(MEMBERS_FILE, index=False)
    print("Correção de dependentes-membros concluída")

def calcular_idade(data_nascimento):
    """Calcula a idade com base na data de nascimento"""
    if not data_nascimento:
        return 0
    try:
        nascimento = datetime.strptime(data_nascimento, '%Y-%m-%d').date()
        hoje = date.today()
        idade = hoje.year - nascimento.year - ((hoje.month, hoje.day) < (nascimento.month, nascimento.day))
        return idade
    except:
        return 0

def contar_membros_com_dependentes():
    """Conta todos os membros incluindo dependentes que são membros completos"""
    df_membros = pd.read_csv(MEMBERS_FILE)
    
    total_membros = len(df_membros)
    homens_membros = len(df_membros[df_membros['Sexo'] == 'Masculino'])
    mulheres_membros = len(df_membros[df_membros['Sexo'] == 'Feminino'])
    
    # Conta dependentes simples (que não são membros completos)
    total_dependentes_simples = 0
    for deps in df_membros['Dependentes']:
        if isinstance(deps, str) and deps.strip():
            try:
                deps_list = json.loads(deps)
                for dep in deps_list:
                    # Se não tem 'tipo' ou tipo é 'simples', conta como dependente simples
                    if dep.get('tipo', 'simples') == 'simples':
                        total_dependentes_simples += 1
            except:
                # Formato antigo - conta como dependente simples
                if isinstance(deps_list, list):
                    total_dependentes_simples += len(deps_list)
    
    # Conta dependentes das pessoas não-membros
    df_pessoas = pd.read_csv(PESSOAS_FILE)
    for deps in df_pessoas['Dependentes']:
        if isinstance(deps, str) and deps.strip():
            try:
                deps_list = json.loads(deps)
                for dep in deps_list:
                    if dep.get('tipo', 'simples') == 'simples':
                        total_dependentes_simples += 1
            except:
                if isinstance(deps_list, list):
                    total_dependentes_simples += len(deps_list)
    
    return total_membros, homens_membros, mulheres_membros, total_dependentes_simples

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

def cadastrar_dependente_como_membro(dados_dependente, id_responsavel):
    """CORRIGIDO: Cadastra um dependente como membro completo"""
    df_membros = pd.read_csv(MEMBERS_FILE)
    
    novo_membro = pd.DataFrame([[
        dados_dependente['nome'],
        dados_dependente['nascimento'],
        dados_dependente['sexo'],
        dados_dependente['estado_civil'],
        dados_dependente['rua'],
        dados_dependente['numero'],
        dados_dependente['bairro'],
        dados_dependente['data_batismo'],
        dados_dependente['batismo_outra_igreja'],
        dados_dependente['nome_igreja'],
        json.dumps([]),  # Dependentes vazios inicialmente
        'Sim',  # É Dependente
        str(id_responsavel)  # ID do Responsável
    ]], columns=['Nome', 'Nascimento', 'Sexo', 'Estado Civil', 'Rua', 'Número', 'Bairro',
                 'Data do Batismo', 'Batismo em Outra Igreja', 'Nome da Igreja', 'Dependentes',
                 'É Dependente', 'ID Responsável'])
    
    df_membros = pd.concat([df_membros, novo_membro], ignore_index=True)
    df_membros.to_csv(MEMBERS_FILE, index=False)
    
    return len(df_membros) - 1  # Retorna o índice do novo membro

def alterar_dependente_para_membro(id_responsavel, nome_dependente, dados_completos):
    """NOVA FUNÇÃO: Converte um dependente simples em dependente-membro"""
    df_membros = pd.read_csv(MEMBERS_FILE)
    
    # Encontrar o membro responsável
    if id_responsavel >= len(df_membros):
        return False, "Membro responsável não encontrado"
    
    membro_responsavel = df_membros.iloc[id_responsavel]
    dependentes = []
    
    if isinstance(membro_responsavel['Dependentes'], str) and membro_responsavel['Dependentes'].strip():
        try:
            dependentes = json.loads(membro_responsavel['Dependentes'])
        except:
            return False, "Erro ao processar dependentes"
    
    # Encontrar o dependente específico
    dependente_encontrado = None
    for i, dep in enumerate(dependentes):
        if dep.get('Nome') == nome_dependente and dep.get('tipo', 'simples') == 'simples':
            dependente_encontrado = i
            break
    
    if dependente_encontrado is None:
        return False, "Dependente não encontrado ou já é membro"
    
    # Criar o novo membro
    id_novo_membro = cadastrar_dependente_como_membro(dados_completos, id_responsavel)
    
    # Atualizar a lista de dependentes do responsável
    dependentes[dependente_encontrado] = {
        "tipo": "membro",
        "Nome": nome_dependente,
        "ID_Membro": id_novo_membro
    }
    
    # Salvar as alterações
    df_membros = pd.read_csv(MEMBERS_FILE)  # Recarregar após inserção
    df_membros.at[id_responsavel, 'Dependentes'] = json.dumps(dependentes)
    df_membros.to_csv(MEMBERS_FILE, index=False)
    
    return True, f"Dependente {nome_dependente} convertido para membro com sucesso"

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
    
    # Migra dados existentes se necessário
    migrar_dados_existentes()
    
    # Carrega dados dos membros com nova contagem
    total_membros, homens_membros, mulheres_membros, total_dependentes = contar_membros_com_dependentes()
    
    # Carrega dados das pessoas (não membros)
    df_pessoas = pd.read_csv(PESSOAS_FILE)
    total_pessoas = len(df_pessoas)
    visitantes = len(df_pessoas[df_pessoas['Situação'] == 'Visitante'])
    novos_convertidos = len(df_pessoas[df_pessoas['Situação'] == 'Novo Convertido'])
    
    # Últimos cadastros
    df_membros = pd.read_csv(MEMBERS_FILE)
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
    """CORRIGIDO: Página de cadastro de membros"""
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
        
        # Migra dados se necessário
        migrar_dados_existentes()
        
        # Processa dependentes
        dependentes = []
        dep_nomes = request.form.getlist('dep_nome')
        dep_tipos = request.form.getlist('dep_tipo')
        
        # Primeiro, salva o membro principal para obter seu ID
        df = pd.read_csv(MEMBERS_FILE)
        novo_membro = pd.DataFrame([[nome, nascimento, sexo, estado_civil, rua, numero, bairro, 
                                     data_batismo, batismo_outra_igreja, nome_igreja, json.dumps([]),
                                     'Não', '']],
                                    columns=['Nome', 'Nascimento', 'Sexo', 'Estado Civil', 'Rua', 'Número', 'Bairro',
                                             'Data do Batismo', 'Batismo em Outra Igreja', 'Nome da Igreja', 'Dependentes',
                                             'É Dependente', 'ID Responsável'])
        df = pd.concat([df, novo_membro], ignore_index=True)
        df.to_csv(MEMBERS_FILE, index=False)
        
        # ID do membro principal (último inserido)
        id_responsavel = len(df) - 1
        
        # Processa dependentes
        if dep_nomes:
            dependentes_finais = []
            
            for i in range(len(dep_nomes)):
                if dep_nomes[i]:  # Verifica se o nome não está vazio
                    tipo_dep = dep_tipos[i] if i < len(dep_tipos) else 'simples'
                    
                    if tipo_dep == 'membro':
                        # Dependente completo - será cadastrado como membro
                        dados_dep = {
                            'nome': dep_nomes[i],
                            'nascimento': request.form.getlist('dep_nascimento')[i] if i < len(request.form.getlist('dep_nascimento')) else "",
                            'sexo': request.form.getlist('dep_sexo')[i] if i < len(request.form.getlist('dep_sexo')) else "",
                            'estado_civil': request.form.getlist('dep_estado_civil')[i] if i < len(request.form.getlist('dep_estado_civil')) else "",
                            'rua': request.form.getlist('dep_rua')[i] if i < len(request.form.getlist('dep_rua')) else rua,
                            'numero': request.form.getlist('dep_numero')[i] if i < len(request.form.getlist('dep_numero')) else numero,
                            'bairro': request.form.getlist('dep_bairro')[i] if i < len(request.form.getlist('dep_bairro')) else bairro,
                            'data_batismo': request.form.getlist('dep_data_batismo')[i] if i < len(request.form.getlist('dep_data_batismo')) else "",
                            'batismo_outra_igreja': request.form.getlist('dep_batismo_outra_igreja')[i] if i < len(request.form.getlist('dep_batismo_outra_igreja')) else "Não",
                            'nome_igreja': request.form.getlist('dep_nome_igreja')[i] if i < len(request.form.getlist('dep_nome_igreja')) else ""
                        }
                        
                        # Cadastra como membro completo
                        id_dep = cadastrar_dependente_como_membro(dados_dep, id_responsavel)
                        
                        # Adiciona referência ao dependente membro
                        dependentes_finais.append({
                            "tipo": "membro",
                            "Nome": dep_nomes[i],
                            "ID_Membro": id_dep
                        })
                    else:
                        # Dependente simples
                        dependente = {
                            "tipo": "simples",
                            "Nome": dep_nomes[i],
                            "Nascimento": request.form.getlist('dep_nascimento')[i] if i < len(request.form.getlist('dep_nascimento')) else "",
                            "Batizado": request.form.getlist('dep_batizado')[i] if i < len(request.form.getlist('dep_batizado')) else "Não"
                        }
                        dependentes_finais.append(dependente)
            
            # Atualiza o membro principal com os dependentes
            df = pd.read_csv(MEMBERS_FILE)
            df.at[id_responsavel, 'Dependentes'] = json.dumps(dependentes_finais)
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

@app.route('/corrigir-dependentes')
def corrigir_dependentes():
    """NOVA ROTA: Rota para executar correção de dependentes-membros"""
    if 'usuario' not in session:
        flash('Você precisa fazer login.', 'error')
        return redirect(url_for('login'))
    
    if session['usuario'] != 'admin':
        flash('Apenas o administrador pode executar correções.', 'error')
        return redirect(url_for('dashboard'))
    
    try:
        corrigir_dependentes_membros()
        flash('Correção de dependentes-membros executada com sucesso!', 'success')
    except Exception as e:
        flash(f'Erro na correção: {str(e)}', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/promover-dependente/<int:id_responsavel>/<nome_dependente>', methods=['GET', 'POST'])
def promover_dependente(id_responsavel, nome_dependente):
    """NOVA ROTA: Promove um dependente simples para dependente-membro"""
    if 'usuario' not in session:
        flash('Você precisa fazer login.', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            # Verificar se todos os campos obrigatórios estão presentes
            campos_obrigatorios = ['nascimento', 'sexo', 'estado_civil', 'rua', 'numero', 'bairro']
            for campo in campos_obrigatorios:
                if not request.form.get(campo):
                    flash(f'O campo {campo} é obrigatório.', 'error')
                    return redirect(request.url)
            
            # Coleta dados do formulário
            dados_completos = {
                'nome': nome_dependente,
                'nascimento': request.form['nascimento'],
                'sexo': request.form['sexo'],
                'estado_civil': request.form['estado_civil'],
                'rua': request.form['rua'],
                'numero': request.form['numero'],
                'bairro': request.form['bairro'],
                'data_batismo': request.form.get('data_batismo', ''),
                'batismo_outra_igreja': request.form.get('batismo_outra_igreja', 'Não'),
                'nome_igreja': request.form.get('nome_igreja', '')
            }
            
            sucesso, mensagem = alterar_dependente_para_membro(id_responsavel, nome_dependente, dados_completos)
            
            if sucesso:
                flash(mensagem, 'success')
                return redirect(url_for('visualizar_membro', indice=id_responsavel))
            else:
                flash(mensagem, 'error')
                
        except Exception as e:
            flash(f'Erro ao processar formulário: {str(e)}', 'error')
    
    # Carregar dados do responsável para pré-preencher endereço
    df_membros = pd.read_csv(MEMBERS_FILE)
    if id_responsavel < len(df_membros):
        responsavel = df_membros.iloc[id_responsavel].to_dict()
        
        # Buscar dados do dependente se já existirem
        dependente_dados = None
        if isinstance(responsavel['Dependentes'], str) and responsavel['Dependentes'].strip():
            try:
                deps = json.loads(responsavel['Dependentes'])
                for dep in deps:
                    if dep.get('Nome') == nome_dependente and dep.get('tipo', 'simples') == 'simples':
                        dependente_dados = dep
                        break
            except:
                pass
        
        return render_template('promover_dependente.html', 
                             responsavel=responsavel, 
                             nome_dependente=nome_dependente,
                             id_responsavel=id_responsavel,
                             dependente_dados=dependente_dados)
    else:
        flash('Membro responsável não encontrado.', 'error')
        return redirect(url_for('listar_membros'))

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
    
    migrar_dados_existentes()
    df = pd.read_csv(MEMBERS_FILE)
    
    # Converte o DataFrame para uma lista de dicionários
    membros = df.to_dict('records')
    
    # Adiciona informações sobre dependentes
    for i, membro in enumerate(membros):
        dependentes_info = []
        if isinstance(membro['Dependentes'], str) and membro['Dependentes'].strip():
            try:
                deps = json.loads(membro['Dependentes'])
                for dep in deps:
                    if dep.get('tipo') == 'membro':
                        dependentes_info.append(f"{dep['Nome']} (Membro)")
                    else:
                        dependentes_info.append(f"{dep['Nome']} (Dependente)")
            except:
                pass
        membro['DependentesInfo'] = ', '.join(dependentes_info) if dependentes_info else 'Nenhum'
    
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
    
    # Processa dependentes
    dependentes_processados = []
    if isinstance(membro['Dependentes'], str) and membro['Dependentes'].strip():
        try:
            deps = json.loads(membro['Dependentes'])
            for dep in deps:
                if dep.get('tipo') == 'membro':
                    # Busca informações completas do dependente membro
                    id_dep = dep.get('ID_Membro')
                    if id_dep is not None and id_dep < len(df):
                        dep_completo = df.iloc[id_dep].to_dict()
                        dep['DadosCompletos'] = dep_completo
                dependentes_processados.append(dep)
        except:
            dependentes_processados = []
    
    membro['DependentesProcessados'] = dependentes_processados
    
    # Verifica se é um dependente
    responsavel_info = None
    if membro.get('É Dependente') == 'Sim' and membro.get('ID Responsável'):
        try:
            id_resp = int(membro['ID Responsável'])
            if id_resp < len(df):
                responsavel_info = df.iloc[id_resp].to_dict()
        except:
            pass
    
    membro['ResponsavelInfo'] = responsavel_info
    
    return render_template('visualizar_membro.html', membro=membro, indice=indice)

@app.route('/membro/editar/<int:indice>', methods=['GET', 'POST'])
def editar_membro(indice):
    """CORRIGIDO: Página para editar um membro"""
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
        
        # Processa dependentes (apenas dependentes simples podem ser editados aqui)
        dependentes_finais = []
        dep_nomes = request.form.getlist('dep_nome')
        dep_tipos = request.form.getlist('dep_tipo')
        
        # Primeiro, preservar dependentes que são membros
        membro_atual = df.iloc[indice]
        if isinstance(membro_atual['Dependentes'], str) and membro_atual['Dependentes'].strip():
            try:
                deps_existentes = json.loads(membro_atual['Dependentes'])
                for dep in deps_existentes:
                    if isinstance(dep, dict) and dep.get('tipo') == 'membro':
                        # Preservar dependentes-membros existentes
                        dependentes_finais.append(dep)
            except Exception as e:
                print(f"Erro ao processar dependentes existentes: {e}")
        
        # Adicionar novos dependentes simples
        if dep_nomes:
            for i in range(len(dep_nomes)):
                if dep_nomes[i]:  # Verifica se o nome não está vazio
                    tipo_dep = dep_tipos[i] if i < len(dep_tipos) else 'simples'
                    
                    if tipo_dep == 'simples':
                        dependente = {
                            "tipo": "simples",
                            "Nome": dep_nomes[i],
                            "Nascimento": request.form.getlist('dep_nascimento')[i] if i < len(request.form.getlist('dep_nascimento')) else "",
                            "Batizado": request.form.getlist('dep_batizado')[i] if i < len(request.form.getlist('dep_batizado')) else "Não"
                        }
                        dependentes_finais.append(dependente)
                    elif tipo_dep == 'membro':
                        # Novo dependente-membro
                        try:
                            dados_dep = {
                                'nome': dep_nomes[i],
                                'nascimento': request.form.getlist('dep_nascimento')[i] if i < len(request.form.getlist('dep_nascimento')) else "",
                                'sexo': request.form.getlist('dep_sexo')[i] if i < len(request.form.getlist('dep_sexo')) else "",
                                'estado_civil': request.form.getlist('dep_estado_civil')[i] if i < len(request.form.getlist('dep_estado_civil')) else "",
                                'rua': request.form.getlist('dep_rua')[i] if i < len(request.form.getlist('dep_rua')) else rua,
                                'numero': request.form.getlist('dep_numero')[i] if i < len(request.form.getlist('dep_numero')) else numero,
                                'bairro': request.form.getlist('dep_bairro')[i] if i < len(request.form.getlist('dep_bairro')) else bairro,
                                'data_batismo': request.form.getlist('dep_data_batismo')[i] if i < len(request.form.getlist('dep_data_batismo')) else "",
                                'batismo_outra_igreja': request.form.getlist('dep_batismo_outra_igreja')[i] if i < len(request.form.getlist('dep_batismo_outra_igreja')) else "Não",
                                'nome_igreja': request.form.getlist('dep_nome_igreja')[i] if i < len(request.form.getlist('dep_nome_igreja')) else ""
                            }
                            
                            id_dep = cadastrar_dependente_como_membro(dados_dep, indice)
                            
                            dependentes_finais.append({
                                "tipo": "membro",
                                "Nome": dep_nomes[i],
                                "ID_Membro": id_dep
                            })
                        except Exception as e:
                            flash(f'Erro ao cadastrar dependente-membro {dep_nomes[i]}: {str(e)}', 'error')
        
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
        df.at[indice, 'Dependentes'] = json.dumps(dependentes_finais)
        
        # Salva o DataFrame atualizado
        df.to_csv(MEMBERS_FILE, index=False)
        
        flash('Membro atualizado com sucesso!', 'success')
        return redirect(url_for('visualizar_membro', indice=indice))
    
    # Para requisição GET, busca os dados atuais para edição
    membro = df.iloc[indice].to_dict()
    
    # Converte os dependentes de JSON para lista, separando simples dos membros
    dependentes_simples = []
    dependentes_membros = []
    
    if isinstance(membro['Dependentes'], str) and membro['Dependentes'].strip():
        try:
            deps = json.loads(membro['Dependentes'])
            for dep in deps:
                if isinstance(dep, dict):  # Verifica se é um dicionário
                    if dep.get('tipo') == 'membro':
                        # Buscar dados completos do dependente-membro
                        id_dep = dep.get('ID_Membro')
                        if id_dep is not None and id_dep < len(df):
                            dep_completo = df.iloc[id_dep].to_dict()
                            dep['DadosCompletos'] = dep_completo
                        dependentes_membros.append(dep)
                    else:
                        dependentes_simples.append(dep)
                else:
                    # Formato antigo - converter para novo formato
                    if isinstance(dep, str):
                        dep_dict = {
                            "tipo": "simples",
                            "Nome": dep,
                            "Nascimento": "",
                            "Batizado": "Não"
                        }
                        dependentes_simples.append(dep_dict)
        except Exception as e:
            print(f"Erro ao processar dependentes para edição: {e}")
            # Em caso de erro, inicializar listas vazias
            dependentes_simples = []
            dependentes_membros = []
    
    # Corrigir o nome da variável para compatibilidade com o template
    membro['Dependentes'] = dependentes_simples
    membro['DependentesSimples'] = dependentes_simples
    membro['DependentesMembros'] = dependentes_membros
    
    return render_template('editar_membro.html', membro=membro, indice=indice)
    
    # Para requisição GET, busca os dados atuais para edição
    membro = df.iloc[indice].to_dict()
    
    # Converte os dependentes de JSON para lista, separando simples dos membros
    dependentes_simples = []
    dependentes_membros = []
    
    if isinstance(membro['Dependentes'], str) and membro['Dependentes'].strip():
        try:
            deps = json.loads(membro['Dependentes'])
            for dep in deps:
                if dep.get('tipo') == 'membro':
                    # Buscar dados completos do dependente-membro
                    id_dep = dep.get('ID_Membro')
                    if id_dep is not None and id_dep < len(df):
                        dep_completo = df.iloc[id_dep].to_dict()
                        dep['DadosCompletos'] = dep_completo
                    dependentes_membros.append(dep)
                else:
                    dependentes_simples.append(dep)
        except:
            pass
    
    membro['DependentesSimples'] = dependentes_simples
    membro['DependentesMembros'] = dependentes_membros
    
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
    
    # Verifica se há dependentes que são membros
    membro = df.iloc[indice]
    dependentes_membros = []
    
    if isinstance(membro['Dependentes'], str) and membro['Dependentes'].strip():
        try:
            deps = json.loads(membro['Dependentes'])
            for dep in deps:
                if dep.get('tipo') == 'membro':
                    dependentes_membros.append(dep.get('ID_Membro'))
        except:
            pass
    
    # Remove a linha do DataFrame
    df = df.drop(indice).reset_index(drop=True)
    
    # Atualiza IDs dos dependentes que são membros (remove vinculação)
    for id_dep in dependentes_membros:
        if id_dep is not None and id_dep < len(df):
            df.at[id_dep, 'É Dependente'] = 'Não'
            df.at[id_dep, 'ID Responsável'] = ''
    
    # Salva o DataFrame atualizado
    df.to_csv(MEMBERS_FILE, index=False)
    
    flash('Membro excluído com sucesso!', 'success')
    return redirect(url_for('listar_membros'))

@app.route('/pessoas')
def listar_pessoas():
    """Página para visualizar todas as pessoas cadastradas (não membros)"""
    if 'usuario' not in session:
        flash('Você precisa fazer login para acessar a lista de pessoas.', 'error')
        return redirect(url_for('login'))
    
    # Carrega dados das pessoas
    if not os.path.exists(PESSOAS_FILE):
        init_files()
    
    migrar_dados_existentes()
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
        data_cadastro = date.today().strftime('%Y-%m-%d')
        
        # Migra dados se necessário
        migrar_dados_existentes()
        
        # Processa dependentes
        dependentes = []
        dep_nomes = request.form.getlist('dep_nome')
        if dep_nomes:
            for i in range(len(dep_nomes)):
                if dep_nomes[i]:  # Verifica se o nome não está vazio
                    dependente = {
                        "tipo": "simples",
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
                                        '', 'Não', '', json.dumps(dependentes), 'Não', '']],
                                       columns=['Nome', 'Nascimento', 'Sexo', 'Estado Civil', 'Rua', 'Número', 'Bairro',
                                               'Data do Batismo', 'Batismo em Outra Igreja', 'Nome da Igreja', 'Dependentes',
                                               'É Dependente', 'ID Responsável'])
            df_membros = pd.concat([df_membros, novo_membro], ignore_index=True)
            df_membros.to_csv(MEMBERS_FILE, index=False)
            
            flash('Pessoa cadastrada como membro com sucesso!', 'success')
            return redirect(url_for('listar_membros'))
        else:
            # Salva a nova pessoa no arquivo de pessoas
            df = pd.read_csv(PESSOAS_FILE)
            nova_pessoa = pd.DataFrame([[nome, nascimento, sexo, estado_civil, rua, numero, bairro, 
                                        situacao, observacoes, data_cadastro, json.dumps(dependentes),
                                        'Não', '']],
                                      columns=['Nome', 'Nascimento', 'Sexo', 'Estado Civil', 'Rua', 'Número', 'Bairro',
                                              'Situação', 'Observações', 'Data de Cadastro', 'Dependentes',
                                              'É Dependente', 'ID Responsável'])
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
        try:
            pessoa['Dependentes'] = json.loads(pessoa['Dependentes'])
        except:
            pessoa['Dependentes'] = []
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
                                        '', 'Não', '', json.dumps(dependentes), 'Não', '']],
                                       columns=['Nome', 'Nascimento', 'Sexo', 'Estado Civil', 'Rua', 'Número', 'Bairro',
                                               'Data do Batismo', 'Batismo em Outra Igreja', 'Nome da Igreja', 'Dependentes',
                                               'É Dependente', 'ID Responsável'])
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
        try:
            pessoa['Dependentes'] = json.loads(pessoa['Dependentes'])
        except:
            pessoa['Dependentes'] = []
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
    migrar_dados_existentes()
    app.run(debug=True)