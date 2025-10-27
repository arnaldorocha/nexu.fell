from . import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

# ----------------- Usuários do sistema ----------------- #
class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    senha_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='comum')  # comum ou admin
    last_login = db.Column(db.DateTime, nullable=True)

    # Relacionamentos
    clientes = db.relationship('Cliente', backref='usuario', lazy=True)
    profissionais = db.relationship('Profissional', backref='usuario', lazy=True)
    transacoes = db.relationship('Transacao', backref='usuario', lazy=True)
    metas = db.relationship('MetaFinanceira', backref='usuario', lazy=True)
    avisos = db.relationship('Aviso', backref='usuario', lazy=True)
    agendamentos = db.relationship('Agendamento', backref='usuario', lazy=True)
    vendas_produtos = db.relationship('VendaProduto', backref='usuario', lazy=True)
    movimentos = db.relationship('MovimentoCaixa', backref='usuario', lazy=True)
    caixas_abertos = db.relationship('Caixa', foreign_keys='Caixa.usuario_abertura', backref='usuario_abertura_ref', lazy=True)
    caixas_fechados = db.relationship('Caixa', foreign_keys='Caixa.usuario_fechamento', backref='usuario_fechamento_ref', lazy=True)
    servicos_realizados = db.relationship('ServicoRealizado', backref='usuario', lazy=True)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def checar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

# ----------------- Clientes ----------------- #
class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    telefone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    observacoes = db.Column(db.Text)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)

    agendamentos = db.relationship('Agendamento', backref='cliente', lazy=True)
    servicos_realizados = db.relationship('ServicoRealizado', backref='cliente', lazy=True)
    ordens_servico = db.relationship('OrdemServico', backref='cliente', lazy=True)
    notas_fiscais = db.relationship('NotaFiscal', backref='cliente', lazy=True)

# ----------------- Profissionais ----------------- #
class Profissional(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    especialidades = db.Column(db.String(200))
    disponibilidade = db.Column(db.String(200))
    contato = db.Column(db.String(100))
    percentual_comissao = db.Column(db.Float, default=0.0)

    agendamentos = db.relationship('Agendamento', backref='profissional', lazy=True)
    servicos_realizados = db.relationship('ServicoRealizado', backref='profissional', lazy=True)

# ----------------- Serviços ----------------- #
class Servico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    preco_padrao = db.Column(db.Float)

    agendamentos = db.relationship('Agendamento', backref='servico', lazy=True)
    servicos_realizados = db.relationship('ServicoRealizado', backref='servico', lazy=True)
    ordens_servico = db.relationship('OrdemServico', backref='servico', lazy=True)

# ----------------- Produtos ----------------- #
class Produto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    preco = db.Column(db.Float, nullable=False)
    quantidade = db.Column(db.Integer, default=0)
    quantidade_minima = db.Column(db.Integer, default=0)

    vendas = db.relationship('VendaProduto', backref='produto', lazy=True)
    movimentacoes = db.relationship('MovimentacaoEstoque', backref='produto', lazy=True)
    produtos_usados = db.relationship('ProdutoUsado', backref='produto', lazy=True)

# ----------------- Agendamentos ----------------- #
class Agendamento(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    profissional_id = db.Column(db.Integer, db.ForeignKey('profissional.id'))
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'))
    data = db.Column(db.Date)
    hora = db.Column(db.String(10))
    valor_pago = db.Column(db.Float)
    forma_pagamento = db.Column(db.String(20))
    status = db.Column(db.String(20), default='agendado')
    observacao = db.Column(db.Text)
    custo = db.Column(db.Float, default=0.0)

# ----------------- Venda de produtos ----------------- #
class VendaProduto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    valor_unitario = db.Column(db.Float, nullable=False)
    desconto_percentual = db.Column(db.Float, default=0)
    valor_total = db.Column(db.Float, nullable=False)
    data = db.Column(db.DateTime, default=datetime.utcnow)

# ----------------- Movimentações de caixa ----------------- #
class MovimentoCaixa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(10))
    forma_pagamento = db.Column(db.String(20))
    valor = db.Column(db.Float)
    descricao = db.Column(db.String(200))
    data = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)

# ----------------- Caixa ----------------- #
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

# ----------------- Movimentação de estoque ----------------- #
class MovimentacaoEstoque(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'))
    tipo = db.Column(db.String(10))
    quantidade = db.Column(db.Integer)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    observacao = db.Column(db.String(200))

# ----------------- Serviços realizados ----------------- #
class ServicoRealizado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    profissional_id = db.Column(db.Integer, db.ForeignKey('profissional.id'))
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'))
    data = db.Column(db.Date)
    valor_pago = db.Column(db.Float)
    produtos_usados = db.relationship('ProdutoUsado', backref='servico_realizado', lazy=True)

# ----------------- Produtos usados em serviços ----------------- #
class ProdutoUsado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    servico_realizado_id = db.Column(db.Integer, db.ForeignKey('servico_realizado.id'))
    produto_id = db.Column(db.Integer, db.ForeignKey('produto.id'))
    quantidade = db.Column(db.Integer)

# ----------------- Ordem de Serviço ----------------- #
class OrdemServico(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    servico_id = db.Column(db.Integer, db.ForeignKey('servico.id'))
    data = db.Column(db.DateTime, default=datetime.utcnow)
    descricao = db.Column(db.Text)
    status = db.Column(db.String(20))

# ----------------- Nota Fiscal ----------------- #
class NotaFiscal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'))
    valor_total = db.Column(db.Float)
    data_emissao = db.Column(db.DateTime, default=datetime.utcnow)
    descricao = db.Column(db.String(200))

# ----------------- Transações ----------------- #
class Transacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    tipo = db.Column(db.String(10))
    valor = db.Column(db.Float)
    descricao = db.Column(db.String(200))
    data = db.Column(db.DateTime, default=datetime.utcnow)

# ----------------- Metas Financeiras ----------------- #
class MetaFinanceira(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    titulo = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Float, nullable=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

# ----------------- Avisos ----------------- #
class Aviso(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    titulo = db.Column(db.String(100))
    data_vencimento = db.Column(db.Date)
    valor = db.Column(db.Float)
    tipo = db.Column(db.String(10))
    pago = db.Column(db.Boolean, default=False)

# ----------------- Backup Log ----------------- #
class BackupLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50))
    caminho = db.Column(db.String(200))
