from app import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Usuários do sistema
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    senha_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user')

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def checar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

# Clientes
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    observacoes = db.Column(db.Text)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)

# Profissionais
class Profissional(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    especialidades = db.Column(db.String(200))
    disponibilidade = db.Column(db.String(200))
    contato = db.Column(db.String(100))
    percentual_comissao = db.Column(db.Float, default=0.0)

# Serviços cadastráveis
class Servico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    preco_padrao = db.Column(db.Float)

# Agendamentos de clientes
class Agendamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    profissional_id = db.Column(db.Integer, db.ForeignKey('profissional.id'))
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'))  
    data = db.Column(db.Date)
    hora = db.Column(db.String(10))
    valor_pago = db.Column(db.Float)
    forma_pagamento = db.Column(db.String(20))  
    status = db.Column(db.String(20), default='agendado')
    observacao = db.Column(db.Text)

    cliente = db.relationship('Cliente', backref='agendamentos')
    profissional = db.relationship('Profissional', backref='agendamentos')
    servico = db.relationship('Servico', backref='agendamentos')  
    
# Produtos cadastrados
class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    preco = db.Column(db.Float, nullable=False)
    quantidade = db.Column(db.Integer, default=0)
    quantidade_minima = db.Column(db.Integer, default=0)

# Movimentações de caixa
class MovimentoCaixa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(10))  # entrada ou saida
    forma_pagamento = db.Column(db.String(20))  # pix, cartao_debito, cartao_credito, dinheiro
    valor = db.Column(db.Float)
    descricao = db.Column(db.String(200))
    data = db.Column(db.DateTime, default=datetime.utcnow)

class Caixa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_abertura = db.Column(db.DateTime, default=datetime.utcnow)
    data_fechamento = db.Column(db.DateTime, nullable=True)
    saldo_inicial = db.Column(db.Float, default=0)
    saldo_final = db.Column(db.Float, default=0)
    status = db.Column(db.String(10), default='aberto')
    usuario_abertura = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    usuario_fechamento = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    observacoes = db.Column(db.Text)

class VendaProduto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'))
    quantidade = db.Column(db.Integer, nullable=False)
    valor_unitario = db.Column(db.Float, nullable=False)
    desconto_percentual = db.Column(db.Float, default=0)
    valor_total = db.Column(db.Float, nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)

    produto = db.relationship('Produto')

# Transações vinculadas ao usuário
class Transacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    tipo = db.Column(db.String(10))
    valor = db.Column(db.Float)
    descricao = db.Column(db.String(200))
    data = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.relationship('Usuario', backref='transacoes')

# Metas financeiras
class MetaFinanceira(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    titulo = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    usuario = db.relationship('Usuario', backref='metas')

# Avisos de contas a pagar/receber
class Aviso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    titulo = db.Column(db.String(100))
    data_vencimento = db.Column(db.Date)
    valor = db.Column(db.Float)
    tipo = db.Column(db.String(10))  # entrada ou saida
    pago = db.Column(db.Boolean, default=False)
    usuario = db.relationship('Usuario', backref='avisos')

# Serviços realizados
class ServicoRealizado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    profissional_id = db.Column(db.Integer, db.ForeignKey('profissional.id'))
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'))
    data = db.Column(db.Date)
    valor_pago = db.Column(db.Float)

    cliente = db.relationship('Cliente')
    profissional = db.relationship('Profissional')
    servico = db.relationship('Servico')

# Produtos usados em serviços
class ProdutoUsado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    servico_realizado_id = db.Column(db.Integer, db.ForeignKey('servico_realizado.id'))
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'))
    quantidade = db.Column(db.Integer)

# Controle de estoque
class MovimentacaoEstoque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'))
    tipo = db.Column(db.String(10))  # entrada ou saida
    quantidade = db.Column(db.Integer)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    observacao = db.Column(db.String(200))

# Simulação de backups diários
class BackupLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50))  # sucesso, erro etc.
    caminho = db.Column(db.String(200))

# Ordem de Serviço
class OrdemServico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'))
    data = db.Column(db.DateTime, default=datetime.utcnow)
    descricao = db.Column(db.Text)
    status = db.Column(db.String(20))  # aberta, em andamento, concluída

# Nota Fiscal (simplificada)
class NotaFiscal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    valor_total = db.Column(db.Float)
    data_emissao = db.Column(db.DateTime, default=datetime.utcnow)
    descricao = db.Column(db.String(200))
