from flask import render_template, request, redirect, url_for, session, flash, jsonify, make_response
from app import app, db
from app.models import Usuario, Cliente, Profissional, Produto, VendaProduto, Agendamento, MovimentoCaixa, Caixa, Servico, OrdemServico, MovimentacaoEstoque
from sqlalchemy import func
from xhtml2pdf import pisa
from io import BytesIO
from datetime import datetime, date, timedelta
from functools import wraps
import csv
import io
from flask import make_response

# ---------------- DECORADOR DE LOGIN ---------------- #
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Faça login para continuar", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ---------------- ROTAS DE AUTENTICAÇÃO ---------------- #
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = Usuario.query.filter_by(username=username).first()
        if user and user.checar_senha(password):
            session['user_id'] = user.id
            session['role'] = user.role
            return redirect(url_for('dashboard'))
        flash('Usuário ou senha inválidos', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash("Logout realizado com sucesso!", "success")
    return redirect(url_for('login'))

@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        if not username or not password:
            flash('Preencha todos os campos.', 'warning')
            return render_template('cadastro.html')
        if Usuario.query.filter_by(username=username).first():
            flash('Usuário já existe.', 'danger')
            return render_template('cadastro.html')
        usuario = Usuario(username=username)
        usuario.set_senha(password)
        db.session.add(usuario)
        db.session.commit()
        flash('Usuário cadastrado com sucesso!', 'success')
        return redirect(url_for('login'))
    return render_template('cadastro.html')

# ---------------- DASHBOARD ---------------- #
@app.route('/dashboard')
@login_required
def dashboard():
    periodo = request.args.get('periodo', 'mes')
    hoje = date.today()
    data_inicio = data_fim = hoje

    if periodo == 'dia':
        pass
    elif periodo == 'semana':
        data_inicio = hoje - timedelta(days=hoje.weekday())
    elif periodo == 'mes':
        data_inicio = hoje.replace(day=1)
    elif periodo == 'ano':
        data_inicio = date(hoje.year, 1, 1)
    elif periodo == 'personalizado':
        try:
            data_inicio = datetime.strptime(request.args.get('data_inicio'), "%Y-%m-%d").date()
            data_fim = datetime.strptime(request.args.get('data_fim'), "%Y-%m-%d").date()
        except Exception:
            flash("Datas inválidas, exibindo o dia atual.", "warning")

    filtro_data = MovimentoCaixa.data.between(data_inicio, data_fim)
    filtro_agendamento = Agendamento.data.between(data_inicio, data_fim)

    # Agendamentos no período
    agendamentos = Agendamento.query.filter(filtro_agendamento).count()

    # Total recebido
    recebimentos = db.session.query(func.sum(MovimentoCaixa.valor))\
        .filter(MovimentoCaixa.tipo == 'entrada')\
        .filter(filtro_data)\
        .scalar() or 0

    # Lucro em serviços = 100% dos serviços concluídos
    lucro_servicos = db.session.query(func.sum(Agendamento.valor_pago))\
        .filter(filtro_agendamento)\
        .filter(Agendamento.status.ilike('%concluido%'))\
        .scalar() or 0

    # Lucro em produtos = venda - custo
    lucro_produtos = 0
    vendas_produtos = db.session.query(MovimentoCaixa).filter(
        MovimentoCaixa.tipo == 'entrada',
        MovimentoCaixa.descricao.like('Venda de produto:%'),
        filtro_data
    ).all()
    for venda in vendas_produtos:
        for produto in Produto.query.all():
            if produto.nome.lower() in venda.descricao.lower():
                lucro_produtos += venda.valor - (produto.preco)

    lucro = lucro_servicos + lucro_produtos

    # Formas de pagamento
    formas_pagamento_labels = ['pix', 'cartao_debito', 'cartao_credito', 'dinheiro']
    formas_pagamento = {label: 0 for label in formas_pagamento_labels}
    pagamentos_raw = db.session.query(
        MovimentoCaixa.forma_pagamento,
        func.sum(MovimentoCaixa.valor)
    ).filter(MovimentoCaixa.tipo == 'entrada')\
     .filter(filtro_data)\
     .group_by(MovimentoCaixa.forma_pagamento).all()
    for forma, valor in pagamentos_raw:
        if forma in formas_pagamento:
            formas_pagamento[forma] = valor or 0

    # Faturamento mensal (fixo - últimos 6 meses, independente do filtro)
    faturamento_mensal = []
    meses = []
    for i in range(5, -1, -1):
        primeiro_dia = (hoje.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
        ultimo_dia = (primeiro_dia.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        total_mes = db.session.query(func.sum(MovimentoCaixa.valor))\
            .filter(MovimentoCaixa.tipo == 'entrada')\
            .filter(MovimentoCaixa.data.between(primeiro_dia, ultimo_dia))\
            .scalar() or 0
        faturamento_mensal.append(total_mes)
        meses.append(primeiro_dia.strftime('%b'))

    # Faturamento por funcionário
    faturamento_funcionario_raw = db.session.query(
        Profissional.nome,
        func.sum(Agendamento.valor_pago)
    ).join(Agendamento, Profissional.id == Agendamento.profissional_id)\
     .filter(filtro_agendamento)\
     .group_by(Profissional.nome).all()
    faturamento_funcionario = {nome: valor or 0 for nome, valor in faturamento_funcionario_raw}

    # Faturamento por serviço
    faturamento_servico_raw = db.session.query(
        Servico.nome,
        func.sum(Agendamento.valor_pago)
    ).join(Agendamento, Servico.id == Agendamento.servico_id)\
     .filter(filtro_agendamento)\
     .group_by(Servico.nome).all()
    faturamento_servico = {nome: valor or 0 for nome, valor in faturamento_servico_raw}

    # Faturamento por produto
    faturamento_produto_raw = db.session.query(
        Produto.nome,
        func.sum(MovimentoCaixa.valor)
    ).filter(MovimentoCaixa.tipo == 'entrada')\
     .filter(MovimentoCaixa.descricao.like('Venda de produto:%'))\
     .filter(filtro_data)\
     .group_by(Produto.nome).all()
    faturamento_produto = {nome: valor or 0 for nome, valor in faturamento_produto_raw}

    # Caso sem vendas no caixa, calcula por movimentação de estoque
    if not faturamento_produto:
        faturamento_produto_alt = db.session.query(
            Produto.nome,
            func.sum(Produto.preco * MovimentacaoEstoque.quantidade)
        ).join(MovimentacaoEstoque)\
         .filter(MovimentacaoEstoque.tipo == 'saida')\
         .group_by(Produto.nome).all()
        faturamento_produto = {nome: valor or 0 for nome, valor in faturamento_produto_alt}

    total_servico = sum(faturamento_servico.values())
    total_produto = sum(faturamento_produto.values())
    comparativo_servico_produto = [total_servico, total_produto]

    return render_template('dashboard.html',
        agendamentos=agendamentos,
        recebimentos=recebimentos,
        lucro=lucro,
        formas_pagamento=formas_pagamento,
        meses=meses,
        faturamento_mensal=faturamento_mensal,
        faturamento_funcionario=faturamento_funcionario,
        faturamento_servico=faturamento_servico,
        faturamento_produto=faturamento_produto,
        total_servico=total_servico,
        total_produto=total_produto,
        comparativo_servico_produto=comparativo_servico_produto,
        periodo=periodo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        active_page='dashboard'
    )

# ---------------- CLIENTES ---------------- #
@app.route('/clientes')
@login_required
def listar_clientes():
    clientes = Cliente.query.order_by(Cliente.data_cadastro.desc()).all()
    profissionais = Profissional.query.order_by(Profissional.nome).all()
    servicos = Servico.query.all()
    return render_template('clientes/listar.html', clientes=clientes, profissionais=profissionais, servicos=servicos)

@app.route('/clientes/novo', methods=['GET', 'POST'])
@login_required
def novo_cliente():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        telefone = request.form.get('telefone', '').strip()
        email = request.form.get('email', '').strip()
        observacoes = request.form.get('observacoes', '').strip()
        if not nome or not telefone:
            flash("Nome e telefone são obrigatórios.", "warning")
            return render_template('clientes/form.html', cliente=None)
        cliente = Cliente(nome=nome, telefone=telefone, email=email, observacoes=observacoes)
        db.session.add(cliente)
        db.session.commit()
        flash("Cliente cadastrado com sucesso!", "success")
        return redirect(url_for('listar_clientes'))
    return render_template('clientes/form.html', cliente=None)

@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    if request.method == 'POST':
        cliente.nome = request.form.get('nome', '').strip()
        cliente.telefone = request.form.get('telefone', '').strip()
        cliente.email = request.form.get('email', '').strip()
        cliente.observacoes = request.form.get('observacoes', '').strip()
        db.session.commit()
        flash("Cliente atualizado com sucesso!", "success")
        return redirect(url_for('listar_clientes'))
    return render_template('clientes/form.html', cliente=cliente)

@app.route('/clientes/excluir/<int:id>')
@login_required
def excluir_cliente(id):
    cliente = Cliente.query.get_or_404(id)
    db.session.delete(cliente)
    db.session.commit()
    flash("Cliente excluído com sucesso!", "success")
    return redirect(url_for('listar_clientes'))

# ---------------- PROFISSIONAIS ---------------- #
@app.route('/profissionais')
@login_required
def listar_profissionais():
    profissionais = Profissional.query.all()
    return render_template('profissionais/listar.html', profissionais=profissionais)

@app.route('/profissionais/novo', methods=['GET', 'POST'])
@login_required
def novo_profissional():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        especialidades = request.form.get('especialidades', '').strip()
        disponibilidade = request.form.get('disponibilidade', '').strip()
        contato = request.form.get('contato', '').strip()
        if not nome:
            flash("Nome é obrigatório.", "warning")
            return render_template('profissionais/form.html', profissional=None)
        prof = Profissional(nome=nome, especialidades=especialidades, disponibilidade=disponibilidade, contato=contato)
        db.session.add(prof)
        db.session.commit()
        flash("Profissional cadastrado!", "success")
        return redirect(url_for('listar_profissionais'))
    return render_template('profissionais/form.html', profissional=None)

@app.route('/profissionais/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_profissional(id):
    profissional = Profissional.query.get_or_404(id)
    if request.method == 'POST':
        profissional.nome = request.form.get('nome', '').strip()
        profissional.especialidades = request.form.get('especialidades', '').strip()
        profissional.disponibilidade = request.form.get('disponibilidade', '').strip()
        profissional.contato = request.form.get('contato', '').strip()
        db.session.commit()
        flash("Profissional atualizado!", "success")
        return redirect(url_for('listar_profissionais'))
    return render_template('profissionais/form.html', profissional=profissional)

@app.route('/profissionais/excluir/<int:id>')
@login_required
def excluir_profissional(id):
    profissional = Profissional.query.get_or_404(id)
    db.session.delete(profissional)
    db.session.commit()
    flash("Profissional excluído!", "success")
    return redirect(url_for('listar_profissionais'))

# ---------------- SERVICOS ---------------- #
@app.route('/servicos')
@login_required
def listar_servicos():
    servicos = Servico.query.order_by(Servico.nome).all()
    return render_template('servicos/listar.html', servicos=servicos)

@app.route('/servicos/novo', methods=['GET', 'POST'])
@login_required
def novo_servico():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        preco = request.form.get('preco', '0').replace(',', '.')
        descricao = request.form.get('descricao', '').strip()
        if not nome or not preco:
            flash("Nome e preço são obrigatórios.", "warning")
            return render_template('servicos/form.html', servico=None)
        s = Servico(nome=nome, preco_padrao=float(preco), descricao=descricao)
        db.session.add(s)
        db.session.commit()
        flash("Serviço cadastrado!", "success")
        return redirect(url_for('listar_servicos'))
    return render_template('servicos/form.html', servico=None)

@app.route('/servicos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_servico(id):
    servico = Servico.query.get_or_404(id)
    if request.method == 'POST':
        servico.nome = request.form.get('nome', '').strip()
        servico.preco_padrao = float(request.form.get('preco', '0').replace(',', '.'))
        servico.descricao = request.form.get('descricao', '').strip()
        db.session.commit()
        flash("Serviço atualizado!", "success")
        return redirect(url_for('listar_servicos'))
    return render_template('servicos/form.html', servico=servico)

@app.route('/servicos/excluir/<int:id>')
@login_required
def excluir_servico(id):
    servico = Servico.query.get_or_404(id)
    db.session.delete(servico)
    db.session.commit()
    flash("Serviço excluído!", "success")
    return redirect(url_for('listar_servicos'))

# ---------------- ORDENS DE SERVIÇO ---------------- #
@app.route('/ordens')
@login_required
def listar_ordens():
    ordens = OrdemServico.query.order_by(OrdemServico.data.desc()).all()
    return render_template('ordens/listar.html', ordens=ordens)

@app.route('/ordens/nova', methods=['GET', 'POST'])
@login_required
def nova_ordem():
    clientes = Cliente.query.all()
    servicos = Servico.query.all()
    if request.method == 'POST':
        ordem = OrdemServico(
            cliente_id=request.form.get('cliente_id'),
            servico_id=request.form.get('servico_id'),
            descricao=request.form.get('descricao', '').strip(),
            status=request.form.get('status', '').strip()
        )
        db.session.add(ordem)
        db.session.commit()
        flash("Ordem de serviço criada!", "success")
        return redirect(url_for('listar_ordens'))
    return render_template('ordens/form.html', clientes=clientes, servicos=servicos, ordem=None)

@app.route('/ordens/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_ordem(id):
    ordem = OrdemServico.query.get_or_404(id)
    clientes = Cliente.query.all()
    servicos = Servico.query.all()
    if request.method == 'POST':
        ordem.cliente_id = request.form.get('cliente_id')
        ordem.servico_id = request.form.get('servico_id')
        ordem.descricao = request.form.get('descricao', '').strip()
        ordem.status = request.form.get('status', '').strip()
        db.session.commit()
        flash("Ordem de serviço atualizada!", "success")
        return redirect(url_for('listar_ordens'))
    return render_template('ordens/form.html', ordem=ordem, clientes=clientes, servicos=servicos)

@app.route('/ordens/excluir/<int:id>')
@login_required
def excluir_ordem(id):
    ordem = OrdemServico.query.get_or_404(id)
    db.session.delete(ordem)
    db.session.commit()
    flash("Ordem de serviço excluída!", "success")
    return redirect(url_for('listar_ordens'))

# ---------------- ESTOQUE ---------------- #
@app.route('/estoque/movimentacoes')
@login_required
def listar_movimentacoes_estoque():
    movimentacoes = MovimentacaoEstoque.query.order_by(MovimentacaoEstoque.data.desc()).all()
    return render_template('estoque/listar.html', movimentacoes=movimentacoes)

@app.route('/estoque/nova', methods=['GET', 'POST'])
@login_required
def nova_movimentacao_estoque():
    produtos = Produto.query.all()
    if request.method == 'POST':
        mov = MovimentacaoEstoque(
            produto_id=request.form.get('produto_id'),
            tipo=request.form.get('tipo'),
            quantidade=int(request.form.get('quantidade', 0)),
            observacao=request.form.get('observacao', '').strip()
        )
        db.session.add(mov)
        db.session.commit()
        flash("Movimentação registrada!", "success")
        return redirect(url_for('listar_movimentacoes_estoque'))
    return render_template('estoque/form.html', produtos=produtos)

@app.route('/estoque/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_movimentacao_estoque(id):
    mov = MovimentacaoEstoque.query.get_or_404(id)
    produtos = Produto.query.all()
    if request.method == 'POST':
        mov.produto_id = request.form.get('produto_id')
        mov.tipo = request.form.get('tipo')
        mov.quantidade = int(request.form.get('quantidade', 0))
        mov.observacao = request.form.get('observacao', '').strip()
        db.session.commit()
        flash("Movimentação atualizada!", "success")
        return redirect(url_for('listar_movimentacoes_estoque'))
    return render_template('estoque/form.html', mov=mov, produtos=produtos)

@app.route('/estoque/excluir/<int:id>')
@login_required
def excluir_movimentacao_estoque(id):
    mov = MovimentacaoEstoque.query.get_or_404(id)
    db.session.delete(mov)
    db.session.commit()
    flash("Movimentação excluída!", "success")
    return redirect(url_for('listar_movimentacoes_estoque'))

# ---------------- LEMBRETE ---------------- #
@app.route('/enviar-lembrete/<int:cliente_id>')
@login_required
def enviar_lembrete(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    mensagem = f"Olá, {cliente.nome}! Lembrete: você tem um agendamento em breve no nosso salão."
    telefone = ''.join(filter(str.isdigit, cliente.telefone))
    url_whatsapp = f"https://api.whatsapp.com/send?phone=55{telefone}&text={mensagem}"
    return redirect(url_whatsapp)

# ---------------- PRODUTOS ---------------- #
@app.route('/produtos')
@login_required
def listar_produtos():
    produtos = Produto.query.all()
    return render_template('produtos/listar.html', produtos=produtos)

@app.route('/produtos/novo', methods=['GET', 'POST'])
@login_required
def novo_produto():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        descricao = request.form.get('descricao', '').strip()
        preco = float(request.form.get('preco', '0').replace(',', '.'))
        quantidade = int(request.form.get('quantidade', 0))
        quantidade_minima = int(request.form.get('quantidade_minima', 0))
        if not nome or preco <= 0:
            flash("Nome e preço válidos são obrigatórios.", "warning")
            return render_template('produtos/form.html', produto=None)
        p = Produto(nome=nome, descricao=descricao, preco=preco, quantidade=quantidade, quantidade_minima=quantidade_minima)
        db.session.add(p)
        db.session.commit()
        flash("Produto cadastrado!", "success")
        return redirect(url_for('listar_produtos'))
    return render_template('produtos/form.html', produto=None)

@app.route('/produtos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_produto(id):
    produto = Produto.query.get_or_404(id)
    if request.method == 'POST':
        produto.nome = request.form.get('nome', '').strip()
        produto.descricao = request.form.get('descricao', '').strip()
        produto.preco = float(request.form.get('preco', '0').replace(',', '.'))
        produto.quantidade = int(request.form.get('quantidade', 0))
        produto.quantidade_minima = int(request.form.get('quantidade_minima', 0))
        db.session.commit()
        flash("Produto atualizado!", "success")
        return redirect(url_for('listar_produtos'))
    return render_template('produtos/form.html', produto=produto)

@app.route('/produtos/excluir/<int:id>')
@login_required
def excluir_produto(id):
    produto = Produto.query.get_or_404(id)
    db.session.delete(produto)
    db.session.commit()
    flash("Produto excluído!", "success")
    return redirect(url_for('listar_produtos'))

# ---------------- AGENDAMENTOS ---------------- #
@app.route('/agendamentos')
@login_required
def listar_agendamentos():
    agendamentos = Agendamento.query.order_by(Agendamento.data.desc()).all()
    clientes = Cliente.query.all()
    profissionais = Profissional.query.all()
    servicos = Servico.query.all()
    return render_template('agendamentos/listar.html', agendamentos=agendamentos, clientes=clientes, profissionais=profissionais, servicos=servicos)

@app.route('/agendamentos/novo', methods=['GET', 'POST'])
@login_required
def novo_agendamento():
    clientes = Cliente.query.all()
    profissionais = Profissional.query.all()
    servicos = Servico.query.all()
    if request.method == 'POST':
        try:
            data_convertida = datetime.strptime(request.form.get('data'), "%Y-%m-%d").date()
            ag = Agendamento(
                cliente_id=request.form.get('cliente_id'),
                profissional_id=request.form.get('profissional_id'),
                servico_id=request.form.get('servico_id'),
                data=data_convertida,
                hora=request.form.get('hora'),
                valor_pago=float(request.form.get('valor_pago', 0)),
                status=request.form.get('status', '').strip(),
                observacao=request.form.get('observacao', '').strip(),
                forma_pagamento=request.form.get('forma_pagamento', '').strip()
            )
            db.session.add(ag)
            db.session.commit()
            flash("Agendamento criado!", "success")
            return redirect(url_for('listar_agendamentos'))
        except Exception:
            flash("Erro ao criar agendamento. Verifique os dados.", "danger")
    return render_template('agendamentos/form.html', agendamento=None, clientes=clientes, profissionais=profissionais, servicos=servicos)

@app.route('/agendamentos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_agendamento(id):
    agendamento = Agendamento.query.get_or_404(id)
    clientes = Cliente.query.all()
    profissionais = Profissional.query.all()
    servicos = Servico.query.all()
    if request.method == 'POST':
        agendamento.status = request.form.get('status', '').strip()
        agendamento.cliente_id = request.form.get('cliente_id')
        agendamento.profissional_id = request.form.get('profissional_id')
        agendamento.servico_id = request.form.get('servico_id')
        agendamento.data = datetime.strptime(request.form.get('data'), "%Y-%m-%d").date()
        agendamento.hora = request.form.get('hora')
        agendamento.valor_pago = float(request.form.get('valor_pago', 0))
        agendamento.observacao = request.form.get('observacao', '').strip()
        agendamento.forma_pagamento = request.form.get('forma_pagamento', '').strip()
        if agendamento.status.lower() == 'concluido':
            movimento_existente = MovimentoCaixa.query.filter(
                MovimentoCaixa.descricao.like(f"%Agendamento ID:{agendamento.id}%")
            ).first()
            if not movimento_existente:
                movimento = MovimentoCaixa(
                    tipo='entrada',
                    forma_pagamento=agendamento.forma_pagamento,
                    valor=agendamento.valor_pago,
                    descricao=f"Serviço realizado (Agendamento ID:{agendamento.id}) - Cliente: {agendamento.cliente.nome}"
                )
                db.session.add(movimento)
        db.session.commit()
        flash("Agendamento atualizado com sucesso!", "success")
        return redirect(url_for('listar_agendamentos'))
    return render_template('agendamentos/form.html', agendamento=agendamento, clientes=clientes, profissionais=profissionais, servicos=servicos)

@app.route('/agendamentos/excluir/<int:id>')
@login_required
def excluir_agendamento(id):
    agendamento = Agendamento.query.get_or_404(id)
    db.session.delete(agendamento)
    db.session.commit()
    flash("Agendamento excluído com sucesso!", "success")
    return redirect(url_for('listar_agendamentos'))

@app.route('/agendamento/concluir/<int:id>', methods=['GET', 'POST'])
@login_required
def concluir_agendamento(id):
    agendamento = Agendamento.query.get_or_404(id)
    if request.method == 'POST':
        valor_pago = float(request.form['valor_pago'])
        forma_pagamento = request.form['forma_pagamento']

        # Atualiza status do agendamento
        agendamento.status = 'concluido'
        agendamento.valor_pago = valor_pago
        agendamento.forma_pagamento = forma_pagamento

        # Verifica se já existe entrada no caixa para evitar duplicação
        existe_movimento = MovimentoCaixa.query.filter_by(
            descricao=f"Serviço: {agendamento.servico.nome}",
            valor=valor_pago,
            profissional_id=agendamento.profissional_id
        ).first()

        if not existe_movimento:
            movimento = MovimentoCaixa(
                tipo='entrada',
                valor=valor_pago,
                descricao=f"Serviço: {agendamento.servico.nome}",
                data=datetime.now(),
                forma_pagamento=forma_pagamento,
                profissional_id=agendamento.profissional_id
            )
            db.session.add(movimento)

        db.session.commit()
        flash('Agendamento concluído e registrado no caixa!', 'success')
        return redirect(url_for('listar_agendamentos'))

    return render_template('agendamentos/concluir.html', agendamento=agendamento)

# ---------------- CAIXA ---------------- #
@app.route('/caixa/abrir', methods=['GET', 'POST'])
@login_required
def abrir_caixa():
    if request.method == 'POST':
        saldo_inicial = float(request.form['saldo_inicial'])
        caixa_aberto = Caixa.query.filter_by(status='aberto').first()
        if caixa_aberto:
            flash('Já existe um caixa aberto. Feche antes de abrir outro.', 'warning')
            return redirect(url_for('caixa'))

        novo_caixa = Caixa(
            saldo_inicial=saldo_inicial,
            usuario_abertura=session['user_id'],
            status='aberto'
        )
        db.session.add(novo_caixa)
        db.session.commit()
        flash('Caixa aberto com sucesso!', 'success')
        return redirect(url_for('caixa'))

    return render_template('caixa/abrir.html')

@app.route('/caixa/fechar/<int:id>', methods=['GET', 'POST'])
@login_required
def fechar_caixa(id):
    caixa = Caixa.query.get_or_404(id)
    if caixa.status == 'fechado':
        flash('Este caixa já está fechado.', 'info')
        return redirect(url_for('caixa'))

    if request.method == 'POST':
        caixa.saldo_final = float(request.form['saldo_final'])
        caixa.data_fechamento = datetime.utcnow()
        caixa.status = 'fechado'
        caixa.usuario_fechamento = session['user_id']
        caixa.observacoes = request.form.get('observacoes', '')
        db.session.commit()
        flash('Caixa fechado com sucesso!', 'success')
        return redirect(url_for('caixa'))

    return render_template('caixa/fechar.html', caixa=caixa)

@app.route('/caixa')
@login_required
def caixa():
    movimentos = MovimentoCaixa.query.order_by(MovimentoCaixa.data.desc()).all()
    entradas = sum(m.valor for m in movimentos if m.tipo == 'entrada')
    saidas = sum(m.valor for m in movimentos if m.tipo == 'saida')
    saldo = entradas - saidas

    caixa_aberto = Caixa.query.filter_by(status='aberto').first()
    return render_template('caixa/listar.html', movimentos=movimentos, saldo=saldo, caixa_aberto=caixa_aberto)

@app.route('/caixa/novo', methods=['GET', 'POST'])
@login_required
def novo_movimento():
    produtos = Produto.query.all()
    if request.method == 'POST':
        tipo = request.form.get('tipo')
        forma_pagamento = request.form.get('forma_pagamento', '')
        descricao = request.form.get('descricao', '').strip()
        valor = float(request.form.get('valor', 0))
        produto_id = request.form.get('produto_id')
        quantidade_vendida = int(request.form.get('quantidade', 0))
        if produto_id and int(produto_id) > 0 and quantidade_vendida > 0:
            produto = Produto.query.get(int(produto_id))
            if produto and produto.quantidade >= quantidade_vendida:
                produto.quantidade -= quantidade_vendida
                db.session.commit()
                descricao = f"Venda de produto: {produto.nome} (Qtd: {quantidade_vendida})"
            else:
                flash("Estoque insuficiente.", "danger")
                return render_template('caixa/form.html', movimento=None, produtos=produtos)
        movimento = MovimentoCaixa(
            tipo=tipo,
            forma_pagamento=forma_pagamento,
            valor=valor,
            descricao=descricao
        )
        db.session.add(movimento)
        db.session.commit()
        flash("Movimentação registrada com sucesso!", "success")
        return redirect(url_for('caixa'))
    return render_template('caixa/form.html', movimento=None, produtos=produtos)


@app.route('/caixa/vender', methods=['POST'])
@login_required
def vender_produto():
    produto_id = int(request.form['produto_id'])
    quantidade = int(request.form['quantidade'])

    produto = Produto.query.get_or_404(produto_id)
    if produto.quantidade < quantidade:
        flash('Estoque insuficiente.', 'danger')
        return redirect(url_for('caixa'))

    valor_total = produto.preco * quantidade

    # Movimento no caixa
    movimento = MovimentoCaixa(
        tipo='entrada',
        valor=valor_total,
        descricao=f"Venda de produto: {produto.nome} (x{quantidade})",
        data=datetime.now(),
        forma_pagamento=request.form['forma_pagamento']
    )
    db.session.add(movimento)

    # Baixa no estoque
    produto.quantidade -= quantidade
    movimentacao = MovimentacaoEstoque(
        produto_id=produto.id,
        tipo='saida',
        quantidade=quantidade,
        data=datetime.now(),
        observacao='Venda realizada'
    )
    db.session.add(movimentacao)
    db.session.commit()

    flash('Venda realizada com sucesso!', 'success')
    return redirect(url_for('caixa'))


@app.route('/caixa/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_movimento(id):
    movimento = MovimentoCaixa.query.get_or_404(id)
    if request.method == 'POST':
        movimento.tipo = request.form.get('tipo')
        movimento.valor = float(request.form.get('valor', 0))
        movimento.descricao = request.form.get('descricao', '').strip()
        db.session.commit()
        flash("Movimentação atualizada!", "success")
        return redirect(url_for('caixa'))
    return render_template('caixa/form.html', movimento=movimento)

@app.route('/caixa/excluir/<int:id>')
@login_required
def excluir_movimento(id):
    movimento = MovimentoCaixa.query.get_or_404(id)
    db.session.delete(movimento)
    db.session.commit()
    flash("Movimentação excluída!", "success")
    return redirect(url_for('caixa'))


# ---------------- VENDAS PRODUTO ---------------- #

@app.route('/vendas/produto', methods=['GET', 'POST'])
@login_required
def nova_venda_produto():
    produtos = Produto.query.all()
    if request.method == 'POST':
        produto_id = int(request.form['produto_id'])
        quantidade = int(request.form['quantidade'])
        desconto = float(request.form['desconto'])
        produto = Produto.query.get(produto_id)

        if produto.quantidade < quantidade:
            flash('Estoque insuficiente!', 'danger')
            return redirect(url_for('nova_venda_produto'))

        valor_unitario = produto.preco
        valor_com_desconto = valor_unitario - (valor_unitario * desconto / 100)
        total = quantidade * valor_com_desconto

        # Registrar venda
        venda = VendaProduto(
            produto_id=produto_id,
            quantidade=quantidade,
            valor_unitario=valor_unitario,
            desconto_percentual=desconto,
            valor_total=total
        )
        db.session.add(venda)

        # Baixar estoque
        produto.quantidade -= quantidade
        db.session.commit()

        # Verificar estoque mínimo
        if produto.quantidade <= produto.quantidade_minima:
            flash(f'Estoque baixo para o produto: {produto.nome}', 'warning')

        flash('Venda registrada e estoque atualizado!', 'success')
        return redirect(url_for('caixa'))

    return render_template('caixa/venda_produto.html', produtos=produtos)



# ---------------- RELATÓRIO PDF ---------------- #
@app.route('/relatorios', methods=['GET'])
@login_required
def pagina_relatorios():
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    active_page = 'relatorios'

    # Padrão: últimos 7 dias
    hoje = date.today()
    if not data_inicio or not data_fim:
        data_inicio = (hoje - timedelta(days=7)).strftime('%Y-%m-%d')
        data_fim = hoje.strftime('%Y-%m-%d')

    return render_template(
        'relatorios/index.html',
        data_inicio=data_inicio,
        data_fim=data_fim,
        active_page=active_page
    )


@app.route('/relatorio/agendamentos/pdf')
@login_required
def relatorio_agendamentos_pdf():
    agendamentos = Agendamento.query.order_by(Agendamento.data.desc()).all()
    html = render_template('relatorios/agendamentos_pdf.html', agendamentos=agendamentos)
    pdf = BytesIO()
    pisa.CreatePDF(html, dest=pdf)
    pdf.seek(0)
    response = make_response(pdf.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=relatorio_agendamentos.pdf'
    return response


@app.route('/exportar/faturamento')
@login_required
def exportar_faturamento_csv():
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    if not data_inicio or not data_fim:
        flash('Intervalo de datas inválido.', 'warning')
        return redirect(url_for('pagina_relatorios'))

    inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
    fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)

    movimentos = MovimentoCaixa.query.filter(
        MovimentoCaixa.data.between(inicio, fim)
    ).order_by(MovimentoCaixa.data.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Data', 'Tipo', 'Valor', 'Forma Pagamento', 'Descrição'])

    for m in movimentos:
        writer.writerow([
            m.data.strftime('%d/%m/%Y %H:%M'),
            m.tipo,
            f"{m.valor:.2f}",
            m.forma_pagamento or '',
            m.descricao or ''
        ])

    output.seek(0)
    response = make_response(output.read())
    response.headers['Content-Disposition'] = f'attachment; filename=faturamento_{data_inicio}_a_{data_fim}.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response



@app.route('/exportar/servicos')
@login_required
def exportar_servicos_csv():
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    if not data_inicio or not data_fim:
        flash('Intervalo de datas inválido.', 'warning')
        return redirect(url_for('pagina_relatorios'))

    inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date()
    fim = datetime.strptime(data_fim, "%Y-%m-%d").date()

    agendamentos = Agendamento.query.filter(
        Agendamento.status == 'concluido',
        Agendamento.data.between(inicio, fim)
    ).order_by(Agendamento.data.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Data', 'Cliente', 'Profissional', 'Serviço', 'Valor Pago', 'Forma de Pagamento'])

    for ag in agendamentos:
        writer.writerow([
            ag.data.strftime('%d/%m/%Y'),
            ag.cliente.nome if ag.cliente else '',
            ag.profissional.nome if ag.profissional else '',
            ag.servico.nome if ag.servico else '',
            f"{ag.valor_pago:.2f}" if ag.valor_pago else '0.00',
            ag.forma_pagamento or ''
        ])

    output.seek(0)
    response = make_response(output.read())
    response.headers['Content-Disposition'] = f'attachment; filename=servicos_{data_inicio}_a_{data_fim}.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response


@app.route('/exportar/vendas-produtos')
@login_required
def exportar_vendas_produtos_csv():
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    if not data_inicio or not data_fim:
        flash('Intervalo de datas inválido.', 'warning')
        return redirect(url_for('pagina_relatorios'))

    inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
    fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)

    vendas = VendaProduto.query.filter(
        VendaProduto.data.between(inicio, fim)
    ).order_by(VendaProduto.data.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Data', 'Produto', 'Quantidade', 'Valor Unitário', 'Desconto (%)', 'Valor Total'])

    for v in vendas:
        writer.writerow([
            v.data.strftime('%d/%m/%Y %H:%M'),
            v.produto.nome if v.produto else '',
            v.quantidade,
            f"{v.valor_unitario:.2f}",
            f"{v.desconto_percentual:.2f}",
            f"{v.valor_total:.2f}"
        ])

    output.seek(0)
    response = make_response(output.read())
    response.headers['Content-Disposition'] = f'attachment; filename=vendas_{data_inicio}_a_{data_fim}.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response


@app.route('/exportar/lucro')
@login_required
def exportar_lucro_csv():
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    if not data_inicio or not data_fim:
        flash('Selecione um intervalo de datas válido.', 'warning')
        return redirect(url_for('pagina_relatorios'))

    inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
    fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)  # inclui o dia final

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Data', 'Origem', 'Descrição', 'Valor'])

    total_entradas = 0
    total_saidas = 0

    # Entradas - Serviços
    agendamentos = Agendamento.query.filter(
        Agendamento.status == 'concluido',
        Agendamento.data.between(inicio.date(), fim.date())
    ).all()
    for ag in agendamentos:
        valor = ag.valor_pago or 0
        total_entradas += valor
        writer.writerow([ag.data.strftime('%d/%m/%Y'), 'Serviço', ag.servico.nome if ag.servico else '', f"{valor:.2f}"])

    # Entradas - Produtos
    vendas = VendaProduto.query.filter(VendaProduto.data.between(inicio, fim)).all()
    for v in vendas:
        valor = v.valor_total or 0
        total_entradas += valor
        writer.writerow([v.data.strftime('%d/%m/%Y %H:%M'), 'Produto', v.produto.nome if v.produto else '', f"{valor:.2f}"])

    # Saídas
    writer.writerow([])
    writer.writerow(['-', '-', 'DESPESAS', '-'])

    saidas = MovimentoCaixa.query.filter(
        MovimentoCaixa.tipo == 'saida',
        MovimentoCaixa.data.between(inicio, fim)
    ).all()
    for s in saidas:
        valor = s.valor or 0
        total_saidas += valor
        writer.writerow([s.data.strftime('%d/%m/%Y %H:%M'), 'Despesa', s.descricao, f"-{valor:.2f}"])

    # Totais
    lucro_real = total_entradas - total_saidas
    writer.writerow([])
    writer.writerow(['TOTAL RECEITA', '', '', f"{total_entradas:.2f}"])
    writer.writerow(['TOTAL DESPESAS', '', '', f"-{total_saidas:.2f}"])
    writer.writerow(['LUCRO REAL', '', '', f"{lucro_real:.2f}"])

    output.seek(0)
    response = make_response(output.read())
    response.headers['Content-Disposition'] = f'attachment; filename=lucro_{data_inicio}_a_{data_fim}.csv'
    response.headers['Content-Type'] = 'text/csv'
    return response

