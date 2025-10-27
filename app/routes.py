# routes.py - versão revisada
from flask import (
    render_template, request, redirect, url_for,
    flash, session, abort
)
from app import app, db
from app.models import (
    Usuario, Cliente, Profissional, Produto, VendaProduto,
    Agendamento, MovimentoCaixa, Caixa, Servico,
    OrdemServico, MovimentacaoEstoque
)

from sqlalchemy import func
from datetime import datetime, date, timedelta

# Decorators
from app.decorators import admin_required

# Flask-Login
from flask_login import login_required, current_user, login_user, logout_user

# Imports para PDF
from io import BytesIO
from xhtml2pdf import pisa
from flask import make_response

# ---------------- LOGIN / LOGOUT ---------------- #
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = Usuario.query.filter_by(username=username).first()
        if user and user.checar_senha(password):
            try:
                user.last_login = datetime.utcnow()
                db.session.commit()
            except Exception:
                db.session.rollback()
            login_user(user, remember=False)
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        flash('Usuário ou senha inválidos', 'danger')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.clear()  # garante limpeza completa da sessão
    flash("Logout realizado com sucesso!", "success")
    return redirect(url_for('login'))


# ---------------- ROTA RAIZ ---------------- #
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


# ---------------- CADASTRO ---------------- #
@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            flash('Preencha todos os campos.', 'warning')
            return render_template('cadastro.html')
        if Usuario.query.filter_by(username=username).first():
            flash('Usuário já existe.', 'danger')
            return render_template('cadastro.html')
        
        # Se for o primeiro usuário, torna admin
        role = 'admin' if Usuario.query.first() is None else 'comum'
        
        usuario = Usuario(username=username, role=role)
        usuario.set_senha(password)
        try:
            db.session.add(usuario)
            db.session.commit()
            flash(f'Usuário cadastrado com sucesso! {"Você é o administrador do sistema." if role=="admin" else ""}', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao cadastrar usuário: {e}', 'danger')
    return render_template('cadastro.html')


# ---------------- ADMINISTRAR USUÁRIOS ---------------- #
@app.route('/usuarios')
@login_required
@admin_required
def listar_usuarios():
    usuarios = Usuario.query.order_by(Usuario.username).all()
    return render_template('usuarios/listar.html', usuarios=usuarios, user=current_user)

@app.route('/usuarios/novo', methods=['GET','POST'])
@login_required
@admin_required
def novo_usuario():
    if request.method == 'POST':
        username = request.form.get('username','').strip()
        senha = request.form.get('senha','').strip()
        role = request.form.get('role','comum')
        if not username or not senha:
            flash("Preencha usuário e senha.", "warning")
            return render_template('usuarios/form.html', usuario=None)
        if Usuario.query.filter_by(username=username).first():
            flash("Usuário já existe.", "danger")
            return render_template('usuarios/form.html', usuario=None)
        u = Usuario(username=username, role=role)
        u.set_senha(senha)
        try:
            db.session.add(u)
            db.session.commit()
            flash("Usuário criado!", "success")
            return redirect(url_for('listar_usuarios'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao criar usuário: {e}", "danger")
    return render_template('usuarios/form.html', usuario=None)

@app.route('/usuarios/editar/<int:id>', methods=['GET','POST'])
@login_required
def editar_usuario(id):
    usuario = Usuario.query.get_or_404(id)

    # Usuário comum só pode editar o próprio perfil
    if current_user.role != 'admin' and current_user.id != usuario.id:
        flash("Acesso negado!", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username','').strip()
        senha = request.form.get('senha','').strip()
        role = request.form.get('role','comum')

        if current_user.role == 'admin':
            if username:
                usuario.username = username
            usuario.role = role
        if senha:
            usuario.set_senha(senha)
        try:
            db.session.commit()
            flash("Usuário atualizado!", "success")
            if current_user.role == 'admin':
                return redirect(url_for('listar_usuarios'))
            else:
                return redirect(url_for('meu_perfil'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar usuário: {e}", "danger")
    return render_template('usuarios/form.html', usuario=usuario)

@app.route('/usuarios/excluir/<int:id>')
@login_required
@admin_required
def excluir_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    if usuario.id == current_user.id:
        flash("Você não pode excluir o usuário logado.", "warning")
        return redirect(url_for('listar_usuarios'))
    try:
        db.session.delete(usuario)
        db.session.commit()
        flash("Usuário excluído!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir usuário: {e}", "danger")
    return redirect(url_for('listar_usuarios'))

# --- Página de perfil do usuário ---
@app.route('/meu-perfil')
@login_required
def meu_perfil():
    return render_template('usuarios/perfil.html', usuario=current_user)

# ---------------- DASHBOARD ---------------- #
@app.route('/dashboard')
@login_required
def dashboard():
    hoje = date.today()
    periodo = request.args.get('periodo', 'mes')

    # ---------------- Filtro de período ---------------- #
    data_inicio = data_fim = hoje
    if periodo == 'dia':
        data_inicio = data_fim = hoje
    elif periodo == 'semana':
        data_inicio = hoje - timedelta(days=hoje.weekday())
        data_fim = hoje
    elif periodo == 'mes':
        data_inicio = hoje.replace(day=1)
        data_fim = hoje
    elif periodo == 'ano':
        data_inicio = date(hoje.year, 1, 1)
        data_fim = hoje
    elif periodo == 'personalizado':
        try:
            data_inicio = datetime.strptime(request.args.get('data_inicio'), "%Y-%m-%d").date()
            data_fim = datetime.strptime(request.args.get('data_fim'), "%Y-%m-%d").date()
        except Exception:
            flash("Datas inválidas, exibindo o dia atual.", "warning")
            data_inicio = data_fim = hoje

    # Converter para datetime (MovimentoCaixa.data é DateTime)
    dt_inicio = datetime.combine(data_inicio, datetime.min.time())
    dt_fim = datetime.combine(data_fim, datetime.max.time())

    # ---------------- Filtros base ---------------- #
    filtro_agendamento = Agendamento.data.between(data_inicio, data_fim)
    filtro_venda = VendaProduto.data.between(dt_inicio, dt_fim)
    filtro_caixa = MovimentoCaixa.data.between(dt_inicio, dt_fim)

    # ---------------- Agendamentos ---------------- #
    if current_user.role == 'admin':
        agendamentos = Agendamento.query.filter(filtro_agendamento).count()
    else:
        agendamentos = Agendamento.query.filter(
            filtro_agendamento,
            Agendamento.usuario_id == current_user.id
        ).count()

    # ---------------- Lucro com serviços ---------------- #
    query_serv = db.session.query(
        func.sum(
            func.coalesce(Agendamento.valor_pago, 0) -
            func.coalesce(Agendamento.custo, 0)
        )
    ).filter(filtro_agendamento, Agendamento.status.ilike('%concluido%'))

    if current_user.role != 'admin':
        query_serv = query_serv.filter(Agendamento.usuario_id == current_user.id)

    lucro_servicos = query_serv.scalar() or 0

    # ---------------- Lucro com produtos ---------------- #
    vendas_produtos = VendaProduto.query.filter(filtro_venda)
    if current_user.role != 'admin':
        vendas_produtos = vendas_produtos.filter(VendaProduto.usuario_id == current_user.id)
    vendas_produtos = vendas_produtos.all()

    lucro_produtos = 0
    for venda in vendas_produtos:
        produto = Produto.query.get(venda.produto_id)
        if produto:
            custo_unitario = getattr(produto, 'custo', 0) or 0
            lucro_produtos += (venda.valor_total or 0) - (custo_unitario * (venda.quantidade or 0))

    # ---------------- Lucro total ---------------- #
    lucro_total = (lucro_servicos or 0) + (lucro_produtos or 0)

    # ---------------- Faturamento mensal ---------------- #
    def add_months(dt, months):
        y = dt.year + (dt.month - 1 + months) // 12
        m = (dt.month - 1 + months) % 12 + 1
        return date(y, m, 1)

    faturamento_mensal = []
    meses = []

    for i in range(5, -1, -1):
        primeiro_dia = add_months(hoje.replace(day=1), -i)
        ultimo_dia = add_months(primeiro_dia, 1) - timedelta(days=1)
        meses.append(primeiro_dia.strftime('%b/%Y'))

        # Serviços concluídos no mês
        q_serv = db.session.query(func.sum(func.coalesce(Agendamento.valor_pago, 0)))\
            .filter(Agendamento.data.between(primeiro_dia, ultimo_dia))\
            .filter(Agendamento.status.ilike('%concluido%'))
        if current_user.role != 'admin':
            q_serv = q_serv.filter(Agendamento.usuario_id == current_user.id)
        total_serv = q_serv.scalar() or 0

        # Caixa (entradas)
        dt_mes_inicio = datetime.combine(primeiro_dia, datetime.min.time())
        dt_mes_fim = datetime.combine(ultimo_dia, datetime.max.time())

        q_caixa = db.session.query(func.sum(func.coalesce(MovimentoCaixa.valor, 0)))\
            .filter(MovimentoCaixa.tipo == 'entrada')\
            .filter(MovimentoCaixa.data.between(dt_mes_inicio, dt_mes_fim))
        if current_user.role != 'admin':
            q_caixa = q_caixa.filter(MovimentoCaixa.usuario_id == current_user.id)
        total_caixa = q_caixa.scalar() or 0

        faturamento_mensal.append((total_serv or 0) + (total_caixa or 0))

    # ---------------- Faturamento por funcionário ---------------- #
    faturamento_funcionario = {}
    query_func = db.session.query(
        Agendamento.usuario_id,
        func.sum(func.coalesce(Agendamento.valor_pago, 0))
    ).filter(filtro_agendamento, Agendamento.status.ilike('%concluido%'))\
     .group_by(Agendamento.usuario_id)

    if current_user.role != 'admin':
        query_func = query_func.filter(Agendamento.usuario_id == current_user.id)

    for user_id, valor in query_func.all():
        usuario = Usuario.query.get(user_id)
        if usuario:
            faturamento_funcionario[usuario.username] = valor or 0

    # ---------------- Faturamento por serviço ---------------- #
    faturamento_servico = {}
    query_servico = db.session.query(
        Agendamento.servico_id,
        func.sum(func.coalesce(Agendamento.valor_pago, 0))
    ).filter(filtro_agendamento, Agendamento.status.ilike('%concluido%'))\
     .group_by(Agendamento.servico_id)

    if current_user.role != 'admin':
        query_servico = query_servico.filter(Agendamento.usuario_id == current_user.id)

    for servico_id, valor in query_servico.all():
        agend = Agendamento.query.filter_by(servico_id=servico_id).first()
        if agend and agend.servico:
            faturamento_servico[agend.servico.nome] = faturamento_servico.get(agend.servico.nome, 0) + (valor or 0)

    # ---------------- Faturamento por produto ---------------- #
    faturamento_produto = {}
    for venda in vendas_produtos:
        produto = Produto.query.get(venda.produto_id)
        if produto:
            faturamento_produto[produto.nome] = faturamento_produto.get(produto.nome, 0) + (venda.valor_total or 0)

    # ---------------- Comparativo Serviços x Produtos ---------------- #
    total_servicos = sum(faturamento_servico.values())
    total_produtos = sum(faturamento_produto.values())
    comparativo_servico_produto = [total_servicos, total_produtos]

    # ---------------- Formas de Pagamento ---------------- #
    formas_pagamento_labels = ['pix', 'cartao_debito', 'cartao_credito', 'dinheiro']
    formas_pagamento = {label: 0 for label in formas_pagamento_labels}

    pagamentos_query = MovimentoCaixa.query.filter(MovimentoCaixa.tipo == 'entrada', filtro_caixa)
    if current_user.role != 'admin':
        pagamentos_query = pagamentos_query.filter(MovimentoCaixa.usuario_id == current_user.id)

    pagamentos_query = pagamentos_query.with_entities(
        MovimentoCaixa.forma_pagamento,
        func.sum(func.coalesce(MovimentoCaixa.valor, 0))
    ).group_by(MovimentoCaixa.forma_pagamento)

    for forma, valor in pagamentos_query.all():
        formas_pagamento[forma] = valor or 0

    # ---------------- Renderização ---------------- #
    return render_template(
        'dashboard.html',
        periodo=periodo,
        data_inicio=data_inicio,
        data_fim=data_fim,
        agendamentos=agendamentos,
        faturamento_geral=lucro_total,
        faturamento_mensal=faturamento_mensal,
        meses=meses,
        faturamento_funcionario=faturamento_funcionario,
        faturamento_servico=faturamento_servico,
        faturamento_produto=faturamento_produto,
        comparativo_servico_produto=comparativo_servico_produto,
        formas_pagamento=formas_pagamento
    )

# ---------------- CLIENTES ---------------- #
@app.route('/clientes')
@login_required
def listar_clientes():
    clientes = Cliente.query.filter_by(usuario_id=current_user.id).all()
    profissionais = Profissional.query.filter_by(usuario_id=current_user.id).all()
    servicos = Servico.query.filter_by(usuario_id=current_user.id).all()
    
    despesas = MovimentoCaixa.query.filter_by(usuario_id=current_user.id, tipo='saida').all()
    total_despesas = sum(d.valor for d in despesas)
    
    return render_template('clientes/listar.html',
                           clientes=clientes,
                           profissionais=profissionais,
                           servicos=servicos,
                           despesas=despesas,
                           total_despesas=total_despesas)

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
        cliente = Cliente(
            nome=nome, 
            telefone=telefone, 
            email=email, 
            observacoes=observacoes,
            usuario_id=current_user.id
        )
        try:
            db.session.add(cliente)
            db.session.commit()
            flash("Cliente cadastrado com sucesso!", "success")
            return redirect(url_for('listar_clientes'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao cadastrar cliente: {e}", "danger")
    return render_template('clientes/form.html', cliente=None)

@app.route('/clientes/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_cliente(id):
    cliente = Cliente.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    if request.method == 'POST':
        cliente.nome = request.form.get('nome', '').strip()
        cliente.telefone = request.form.get('telefone', '').strip()
        cliente.email = request.form.get('email', '').strip()
        cliente.observacoes = request.form.get('observacoes', '').strip()
        try:
            db.session.commit()
            flash("Cliente atualizado com sucesso!", "success")
            return redirect(url_for('listar_clientes'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar cliente: {e}", "danger")
    return render_template('clientes/form.html', cliente=cliente)

@app.route('/clientes/excluir/<int:id>')
@login_required
def excluir_cliente(id):
    cliente = Cliente.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    try:
        db.session.delete(cliente)
        db.session.commit()
        flash("Cliente excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir cliente: {e}", "danger")
    return redirect(url_for('listar_clientes'))

# ---------------- PROFISSIONAIS ---------------- #
@app.route('/profissionais')
@login_required
def listar_profissionais():
    profissionais = Profissional.query.filter_by(usuario_id=current_user.id).all()
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
        prof = Profissional(
            nome=nome, 
            especialidades=especialidades, 
            disponibilidade=disponibilidade, 
            contato=contato,
            usuario_id=current_user.id
        )
        try:
            db.session.add(prof)
            db.session.commit()
            flash("Profissional cadastrado!", "success")
            return redirect(url_for('listar_profissionais'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao cadastrar profissional: {e}", "danger")
    return render_template('profissionais/form.html', profissional=None)

@app.route('/profissionais/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_profissional(id):
    profissional = Profissional.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    if request.method == 'POST':
        profissional.nome = request.form.get('nome', '').strip()
        profissional.especialidades = request.form.get('especialidades', '').strip()
        profissional.disponibilidade = request.form.get('disponibilidade', '').strip()
        profissional.contato = request.form.get('contato', '').strip()
        try:
            db.session.commit()
            flash("Profissional atualizado!", "success")
            return redirect(url_for('listar_profissionais'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar profissional: {e}", "danger")
    return render_template('profissionais/form.html', profissional=profissional)

@app.route('/profissionais/excluir/<int:id>')
@login_required
def excluir_profissional(id):
    profissional = Profissional.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    try:
        db.session.delete(profissional)
        db.session.commit()
        flash("Profissional excluído!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir profissional: {e}", "danger")
    return redirect(url_for('listar_profissionais'))

# ---------------- SERVIÇOS ---------------- #
@app.route('/servicos')
@login_required
def listar_servicos():
    servicos = Servico.query.filter_by(usuario_id=current_user.id).order_by(Servico.nome).all()
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
        s = Servico(
            nome=nome, 
            preco_padrao=float(preco), 
            descricao=descricao,
            usuario_id=current_user.id
        )
        try:
            db.session.add(s)
            db.session.commit()
            flash("Serviço cadastrado!", "success")
            return redirect(url_for('listar_servicos'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao cadastrar serviço: {e}", "danger")
    return render_template('servicos/form.html', servico=None)

@app.route('/servicos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_servico(id):
    servico = Servico.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    if request.method == 'POST':
        servico.nome = request.form.get('nome', '').strip()
        servico.preco_padrao = float(request.form.get('preco', '0').replace(',', '.'))
        servico.descricao = request.form.get('descricao', '').strip()
        try:
            db.session.commit()
            flash("Serviço atualizado!", "success")
            return redirect(url_for('listar_servicos'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar serviço: {e}", "danger")
    return render_template('servicos/form.html', servico=servico)

@app.route('/servicos/excluir/<int:id>')
@login_required
def excluir_servico(id):
    servico = Servico.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    try:
        db.session.delete(servico)
        db.session.commit()
        flash("Serviço excluído!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir serviço: {e}", "danger")
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
        try:
            db.session.add(ordem)
            db.session.commit()
            flash("Ordem de serviço criada!", "success")
            return redirect(url_for('listar_ordens'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao criar ordem: {e}", "danger")
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
        try:
            db.session.commit()
            flash("Ordem de serviço atualizada!", "success")
            return redirect(url_for('listar_ordens'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar ordem: {e}", "danger")
    return render_template('ordens/form.html', ordem=ordem, clientes=clientes, servicos=servicos)


@app.route('/ordens/excluir/<int:id>')
@login_required
def excluir_ordem(id):
    ordem = OrdemServico.query.get_or_404(id)
    try:
        db.session.delete(ordem)
        db.session.commit()
        flash("Ordem de serviço excluída!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir ordem: {e}", "danger")
    return redirect(url_for('listar_ordens'))


# ---------------- ESTOQUE ---------------- #
@app.route('/estoque')
@login_required
def estoque():
    # lista só o que tem > 0 (disponível)
    produtos_disponiveis = Produto.query.filter(Produto.quantidade > 0).order_by(Produto.nome).all()
    return render_template('estoque/listar.html', produtos=produtos_disponiveis)


# Rota corrigida para movimentações (não conflitar com /estoque)
@app.route('/estoque/movimentacoes')
@login_required
def listar_movimentacoes_estoque():
    movimentacoes = MovimentacaoEstoque.query.order_by(MovimentacaoEstoque.data.desc()).all()
    return render_template('estoque/listar.html', movimentacoes=movimentacoes, active_page='estoque')


@app.route('/estoque/configurar/<int:produto_id>', methods=['GET','POST'])
@login_required
def configurar_estoque(produto_id):
    produto = Produto.query.get_or_404(produto_id)
    if request.method == 'POST':
        tipo = request.form.get('tipo')  # 'entrada' ou 'saida'
        quantidade = int(request.form.get('quantidade', 0))
        observacao = request.form.get('observacao', '').strip()

        if quantidade <= 0:
            flash('Quantidade inválida.', 'warning')
            return redirect(url_for('configurar_estoque', produto_id=produto_id))

        # Baixa/entrada
        try:
            if tipo == 'entrada':
                produto.quantidade = (produto.quantidade or 0) + quantidade
            else:
                if produto.quantidade < quantidade:
                    flash('Estoque insuficiente para retirada.', 'danger')
                    return redirect(url_for('configurar_estoque', produto_id=produto_id))
                produto.quantidade -= quantidade

            mov = MovimentacaoEstoque(
                produto_id=produto.id,
                tipo=tipo,
                quantidade=quantity,
                observacao=observacao
            )
            db.session.add(mov)
            db.session.commit()
            flash('Estoque atualizado!', 'success')
            return redirect(url_for('estoque'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao atualizar estoque: {e}', 'danger')

    # GET
    return render_template('estoque/configurar.html', produto=produto)


# ---------------- LEMBRETE ---------------- #
@app.route('/enviar-lembrete/<int:cliente_id>')
@login_required
def enviar_lembrete(cliente_id):
    cliente = Cliente.query.get_or_404(cliente_id)
    mensagem = f"Olá, {cliente.nome}! Lembrete: você tem um agendamento em breve no nosso salão."
    telefone = ''.join(filter(str.isdigit, cliente.telefone or ''))
    url_whatsapp = f"https://api.whatsapp.com/send?phone=55{telefone}&text={mensagem}"
    return redirect(url_whatsapp)


# ---------------- PRODUTOS ---------------- #
@app.route('/produtos')
@login_required
def listar_produtos():
    produtos = Produto.query.filter_by(usuario_id=current_user.id).all()
    return render_template('produtos/listar.html', produtos=produtos)

@app.route('/produtos/novo', methods=['GET', 'POST'])
@login_required
def novo_produto():
    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        preco = request.form.get('preco', '0').replace(',', '.')
        descricao = request.form.get('descricao', '').strip()
        quantidade = request.form.get('quantidade', 0)
        if not nome or not preco:
            flash("Nome e preço são obrigatórios.", "warning")
            return render_template('produtos/form.html', produto=None)
        p = Produto(
            nome=nome,
            preco=float(preco),
            descricao=descricao,
            quantidade=int(quantidade),
            usuario_id=current_user.id
        )
        try:
            db.session.add(p)
            db.session.commit()
            flash("Produto cadastrado!", "success")
            return redirect(url_for('listar_produtos'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao cadastrar produto: {e}", "danger")
    return render_template('produtos/form.html', produto=None)

@app.route('/produtos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_produto(id):
    produto = Produto.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    if request.method == 'POST':
        produto.nome = request.form.get('nome', '').strip()
        produto.preco = float(request.form.get('preco', '0').replace(',', '.'))
        produto.descricao = request.form.get('descricao', '').strip()
        produto.quantidade = int(request.form.get('quantidade', 0))
        try:
            db.session.commit()
            flash("Produto atualizado!", "success")
            return redirect(url_for('listar_produtos'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar produto: {e}", "danger")
    return render_template('produtos/form.html', produto=produto)

@app.route('/produtos/excluir/<int:id>')
@login_required
def excluir_produto(id):
    produto = Produto.query.filter_by(id=id, usuario_id=current_user.id).first_or_404()
    try:
        db.session.delete(produto)
        db.session.commit()
        flash("Produto excluído!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir produto: {e}", "danger")
    return redirect(url_for('listar_produtos'))


# ------- DESPESAS (MovimentoCaixa tipo='saida') -------
@app.route('/despesas')
@login_required
def listar_despesas():
    despesas = MovimentoCaixa.query.filter(MovimentoCaixa.tipo == 'saida').order_by(MovimentoCaixa.data.desc()).all()
    
    # Soma total das despesas
    total_despesas = sum(d.valor for d in despesas)
    
    return render_template('despesas/listar.html', despesas=despesas, total_despesas=total_despesas)


@app.route('/despesas/nova', methods=['GET','POST'])
@login_required
def nova_despesa():
    if request.method == 'POST':
        descricao = request.form.get('descricao','').strip()
        try:
            valor = float(request.form.get('valor','0').replace(',','.'))
        except Exception:
            valor = 0.0
        data = request.form.get('data')
        try:
            date_obj = datetime.strptime(data, "%Y-%m-%d %H:%M") if ' ' in data else datetime.strptime(data, "%Y-%m-%d")
        except Exception:
            date_obj = datetime.utcnow()
        desp = MovimentoCaixa(tipo='saida', forma_pagamento=request.form.get('forma_pagamento',''), valor=valor, descricao=descricao, data=date_obj)
        try:
            db.session.add(desp)
            db.session.commit()
            flash("Despesa registrada!", "success")
            return redirect(url_for('listar_despesas'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao registrar despesa: {e}", "danger")
    return render_template('despesas/form.html', despesa=None)


@app.route('/despesas/editar/<int:id>', methods=['GET','POST'])
@login_required
def editar_despesa(id):
    desp = MovimentoCaixa.query.get_or_404(id)
    if desp.tipo != 'saida':
        flash("Despesa não encontrada.", "warning")
        return redirect(url_for('listar_despesas'))
    if request.method == 'POST':
        desp.descricao = request.form.get('descricao','').strip()
        try:
            desp.valor = float(request.form.get('valor','0').replace(',','.'))
        except Exception:
            desp.valor = 0.0
        desp.forma_pagamento = request.form.get('forma_pagamento','')
        try:
            data = request.form.get('data')
            desp.data = datetime.strptime(data, "%Y-%m-%d %H:%M") if ' ' in data else datetime.strptime(data, "%Y-%m-%d")
        except Exception:
            pass
        try:
            db.session.commit()
            flash("Despesa atualizada!", "success")
            return redirect(url_for('listar_despesas'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar despesa: {e}", "danger")
    return render_template('despesas/form.html', despesa=desp)


@app.route('/despesas/excluir/<int:id>')
@login_required
def excluir_despesa(id):
    desp = MovimentoCaixa.query.get_or_404(id)
    if desp.tipo != 'saida':
        flash("Despesa inválida.", "warning")
        return redirect(url_for('listar_despesas'))
    try:
        db.session.delete(desp)
        db.session.commit()
        flash("Despesa excluída!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir despesa: {e}", "danger")
    return redirect(url_for('listar_despesas'))


# ---------------- AGENDAMENTOS ---------------- #
@app.route('/agendamentos')
@login_required
def listar_agendamentos():
    # admin vê tudo, usuário comum só os seus
    if current_user.role == 'admin':
        agendamentos = Agendamento.query.order_by(Agendamento.data.desc()).all()
    else:
        agendamentos = Agendamento.query.filter_by(usuario_id=current_user.id).order_by(Agendamento.data.desc()).all()
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
            data_str = request.form.get('data')
            data_convertida = datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else None
            ag = Agendamento(
                usuario_id=current_user.id,  # atribui usuário logado
                cliente_id=request.form.get('cliente_id'),
                profissional_id=request.form.get('profissional_id'),
                servico_id=request.form.get('servico_id'),
                data=data_convertida,
                hora=request.form.get('hora'),
                valor_pago=float(request.form.get('valor_pago', 0)),
                status=request.form.get('status', '').strip() or 'agendado',
                observacao=request.form.get('observacao', '').strip(),
                forma_pagamento=request.form.get('forma_pagamento', '').strip()
            )
            db.session.add(ag)
            db.session.commit()
            flash("Agendamento criado!", "success")
            return redirect(url_for('listar_agendamentos'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao criar agendamento. Verifique os dados. ({e})", "danger")
    return render_template('agendamentos/form.html', agendamento=None, clientes=clientes, profissionais=profissionais, servicos=servicos)


@app.route('/agendamentos/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_agendamento(id):
    agendamento = Agendamento.query.get_or_404(id)
    # permissão: só dono ou admin
    if agendamento.usuario_id != current_user.id and current_user.role != 'admin':
        flash("Você não tem permissão para editar este agendamento.", "danger")
        return redirect(url_for('listar_agendamentos'))

    clientes = Cliente.query.all()
    profissionais = Profissional.query.all()
    servicos = Servico.query.all()
    if request.method == 'POST':
        try:
            agendamento.status = request.form.get('status', '').strip()
            agendamento.cliente_id = request.form.get('cliente_id')
            agendamento.profissional_id = request.form.get('profissional_id')
            agendamento.servico_id = request.form.get('servico_id')
            data_str = request.form.get('data')
            agendamento.data = datetime.strptime(data_str, "%Y-%m-%d").date() if data_str else agendamento.data
            agendamento.hora = request.form.get('hora')
            agendamento.valor_pago = float(request.form.get('valor_pago', 0))
            agendamento.observacao = request.form.get('observacao', '').strip()
            agendamento.forma_pagamento = request.form.get('forma_pagamento', '').strip()

            # cria movimento no caixa caso mude para concluído
            if agendamento.status.lower() == 'concluido':
                movimento_existente = MovimentoCaixa.query.filter(
                    MovimentoCaixa.descricao.like(f"%Agendamento ID:{agendamento.id}%")
                ).first()
                if not movimento_existente:
                    movimento = MovimentoCaixa(
                        tipo='entrada',
                        forma_pagamento=agendamento.forma_pagamento,
                        valor=agendamento.valor_pago or 0,
                        descricao=f"Serviço realizado (Agendamento ID:{agendamento.id}) - Cliente: {getattr(agendamento.cliente, 'nome', '')}"
                    )
                    db.session.add(movimento)

            db.session.commit()
            flash("Agendamento atualizado com sucesso!", "success")
            return redirect(url_for('listar_agendamentos'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar agendamento: {e}", "danger")
    return render_template('agendamentos/form.html', agendamento=agendamento, clientes=clientes, profissionais=profissionais, servicos=servicos)


@app.route('/agendamentos/excluir/<int:id>')
@login_required
def excluir_agendamento(id):
    agendamento = Agendamento.query.get_or_404(id)
    if agendamento.usuario_id != current_user.id and current_user.role != 'admin':
        flash("Você não tem permissão para excluir este agendamento.", "danger")
        return redirect(url_for('listar_agendamentos'))
    try:
        db.session.delete(agendamento)
        db.session.commit()
        flash("Agendamento excluído com sucesso!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir agendamento: {e}", "danger")
    return redirect(url_for('listar_agendamentos'))


@app.route('/agendamento/concluir/<int:id>', methods=['GET', 'POST'])
@login_required
def concluir_agendamento(id):
    agendamento = Agendamento.query.get_or_404(id)
    if agendamento.usuario_id != current_user.id and current_user.role != 'admin':
        flash("Você não tem permissão para concluir este agendamento.", "danger")
        return redirect(url_for('listar_agendamentos'))

    if request.method == 'POST':
        try:
            valor_pago = float(request.form.get('valor_pago', 0))
            forma_pagamento = request.form.get('forma_pagamento', '')

            # Atualiza status do agendamento
            agendamento.status = 'concluido'
            agendamento.valor_pago = valor_pago
            agendamento.forma_pagamento = forma_pagamento

            # Verifica se já existe entrada no caixa para evitar duplicação
            existe_movimento = MovimentoCaixa.query.filter_by(
                descricao=f"Serviço: {getattr(agendamento.servico, 'nome', '')}",
                valor=valor_pago,
                # possibly add more filters if your schema supports them
            ).first()

            if not existe_movimento:
                movimento = MovimentoCaixa(
                    tipo='entrada',
                    valor=valor_pago,
                    descricao=f"Serviço: {getattr(agendamento.servico, 'nome', '')}",
                    data=datetime.now(),
                    forma_pagamento=forma_pagamento
                )
                db.session.add(movimento)

            db.session.commit()
            flash('Agendamento concluído e registrado no caixa!', 'success')
            return redirect(url_for('listar_agendamentos'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao concluir agendamento: {e}', 'danger')

    return render_template('agendamentos/concluir.html', agendamento=agendamento)


# ---------------- CAIXA ---------------- #
# ---------------- CAIXA ---------------- #
@app.route('/caixa')
@login_required
def caixa():
    # Admin vê todos, usuário comum só os seus movimentos
    if current_user.role == 'admin':
        movimentos = MovimentoCaixa.query.order_by(MovimentoCaixa.data.desc()).all()
    else:
        movimentos = MovimentoCaixa.query.filter_by(usuario_id=current_user.id).order_by(MovimentoCaixa.data.desc()).all()
    
    entradas = sum((m.valor or 0) for m in movimentos if m.tipo == 'entrada')
    saidas = sum((m.valor or 0) for m in movimentos if m.tipo == 'saida')
    saldo = entradas - saidas

    caixa_aberto = Caixa.query.filter_by(status='aberto').first()
    return render_template('caixa/listar.html', movimentos=movimentos, saldo=saldo, caixa_aberto=caixa_aberto)


@app.route('/caixa/abrir', methods=['GET', 'POST'])
@login_required
def abrir_caixa():
    if request.method == 'POST':
        try:
            saldo_inicial = float(request.form.get('saldo_inicial', 0))
        except Exception:
            saldo_inicial = 0.0

        caixa_aberto = Caixa.query.filter_by(status='aberto').first()
        if caixa_aberto:
            flash('Já existe um caixa aberto. Feche antes de abrir outro.', 'warning')
            return redirect(url_for('caixa'))

        novo_caixa = Caixa(
            saldo_inicial=saldo_inicial,
            usuario_abertura=current_user.id,
            status='aberto'
        )
        try:
            db.session.add(novo_caixa)
            db.session.commit()
            flash('Caixa aberto com sucesso!', 'success')
            return redirect(url_for('caixa'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao abrir caixa: {e}', 'danger')

    return render_template('caixa/abrir.html')


@app.route('/caixa/fechar/<int:id>', methods=['GET', 'POST'])
@login_required
def fechar_caixa(id):
    caixa = Caixa.query.get_or_404(id)
    if caixa.status == 'fechado':
        flash('Este caixa já está fechado.', 'info')
        return redirect(url_for('caixa'))

    if request.method == 'POST':
        try:
            caixa.saldo_final = float(request.form.get('saldo_final', 0))
        except Exception:
            caixa.saldo_final = 0.0
        caixa.data_fechamento = datetime.utcnow()
        caixa.status = 'fechado'
        caixa.usuario_fechamento = current_user.id
        caixa.observacoes = request.form.get('observacoes', '')
        try:
            db.session.commit()
            flash('Caixa fechado com sucesso!', 'success')
            return redirect(url_for('caixa'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erro ao fechar caixa: {e}', 'danger')

    return render_template('caixa/fechar.html', caixa=caixa)


@app.route('/caixa/novo', methods=['GET', 'POST'])
@login_required
def novo_movimento():
    produtos = Produto.query.all()
    if request.method == 'POST':
        tipo = request.form.get('tipo')
        forma_pagamento = request.form.get('forma_pagamento', '')
        descricao = request.form.get('descricao', '').strip()
        try:
            valor = float(request.form.get('valor', 0))
        except Exception:
            valor = 0.0
        produto_id = request.form.get('produto_id')
        try:
            quantidade_vendida = int(request.form.get('quantidade', 0))
        except Exception:
            quantidade_vendida = 0

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
            descricao=descricao,
            usuario_id=current_user.id  # <- essencial
        )
        try:
            db.session.add(movimento)
            db.session.commit()
            flash("Movimentação registrada com sucesso!", "success")
            return redirect(url_for('caixa'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao registrar movimentação: {e}", "danger")

    return render_template('caixa/form.html', movimento=None, produtos=produtos)


@app.route('/caixa/vender', methods=['POST'])
@login_required
def vender_produto():
    try:
        produto_id = int(request.form['produto_id'])
        quantidade = int(request.form['quantidade'])
    except Exception:
        flash('Dados inválidos.', 'danger')
        return redirect(url_for('caixa'))

    produto = Produto.query.get_or_404(produto_id)
    if produto.quantidade < quantidade:
        flash('Estoque insuficiente.', 'danger')
        return redirect(url_for('caixa'))

    valor_total = produto.preco * quantidade

    movimento = MovimentoCaixa(
        tipo='entrada',
        valor=valor_total,
        descricao=f"Venda de produto: {produto.nome} (x{quantidade})",
        data=datetime.now(),
        forma_pagamento=request.form.get('forma_pagamento', ''),
        usuario_id=current_user.id  # <- adicionado
    )
    try:
        db.session.add(movimento)

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

        if produto.quantidade <= produto.quantidade_minima:
            flash(f'Estoque baixo para o produto: {produto.nome}', 'warning')

        flash('Venda realizada com sucesso!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao processar venda: {e}', 'danger')

    return redirect(url_for('caixa'))


@app.route('/caixa/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_movimento(id):
    movimento = MovimentoCaixa.query.get_or_404(id)
    if request.method == 'POST':
        movimento.tipo = request.form.get('tipo')
        try:
            movimento.valor = float(request.form.get('valor', 0))
        except Exception:
            movimento.valor = 0.0
        movimento.descricao = request.form.get('descricao', '').strip()
        try:
            db.session.commit()
            flash("Movimentação atualizada!", "success")
            return redirect(url_for('caixa'))
        except Exception as e:
            db.session.rollback()
            flash(f"Erro ao atualizar movimentação: {e}", "danger")

    return render_template('caixa/form.html', movimento=movimento)


@app.route('/caixa/excluir/<int:id>')
@login_required
def excluir_movimento(id):
    movimento = MovimentoCaixa.query.get_or_404(id)
    try:
        db.session.delete(movimento)
        db.session.commit()
        flash("Movimentação excluída!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Erro ao excluir movimentação: {e}", "danger")
    return redirect(url_for('caixa'))


# ---------------- RELATÓRIOS ---------------- #
@app.route('/relatorio/faturamento/geral/pdf')
@login_required
def relatorio_faturamento_geral_pdf():
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')

    hoje = datetime.now()
    if not data_inicio or not data_fim:
        inicio = hoje - timedelta(days=30)
        fim = hoje
    else:
        inicio = datetime.strptime(data_inicio, "%Y-%m-%d")
        fim = datetime.strptime(data_fim, "%Y-%m-%d") + timedelta(days=1)

    query = MovimentoCaixa.query.filter(
        MovimentoCaixa.data >= inicio,
        MovimentoCaixa.data < fim
    )
    # Usuário comum só vê os próprios movimentos
    if current_user.role != 'admin':
        query = query.filter(MovimentoCaixa.usuario_id == current_user.id)

    relatorio = query.order_by(MovimentoCaixa.data.asc()).all()

    total_entradas = sum(m.valor for m in relatorio if m.tipo == 'entrada')
    total_saidas = sum(m.valor for m in relatorio if m.tipo == 'saida')
    lucro = total_entradas - total_saidas

    html = render_template(
        'relatorios/faturamento_geral_pdf.html',
        relatorio=relatorio,
        inicio=inicio.date(),
        fim=(fim - timedelta(days=1)).date(),
        total_entradas=total_entradas,
        total_saidas=total_saidas,
        lucro=lucro
    )

    pdf = BytesIO()
    pisa.CreatePDF(html, dest=pdf)
    pdf.seek(0)
    response = make_response(pdf.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=faturamento_geral.pdf'
    return response

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
# ---------------- RELATÓRIO POR CLIENTE ---------------- #
@app.route('/relatorio/faturamento/por-cliente/pdf')
@login_required
def relatorio_faturamento_por_cliente_pdf():
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    hoje = date.today()

    if not data_inicio or not data_fim:
        inicio = hoje - timedelta(days=30)
        fim = hoje
    else:
        inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        fim = datetime.strptime(data_fim, "%Y-%m-%d").date()

    query = db.session.query(
        Cliente.nome,
        func.sum(Agendamento.valor_pago).label('total'),
        func.count(Agendamento.id).label('qtd')
    ).join(Cliente, Cliente.id == Agendamento.cliente_id)\
     .filter(Agendamento.status.ilike('%concluido%'))\
     .filter(Agendamento.data.between(inicio, fim))

    # Usuário comum só vê os seus agendamentos
    if current_user.role != 'admin':
        query = query.filter(Agendamento.usuario_id == current_user.id)

    agendamentos = query.group_by(Cliente.nome)\
                        .order_by(func.sum(Agendamento.valor_pago).desc())\
                        .all()

    html = render_template(
        'relatorios/faturamento_por_cliente_pdf.html',
        agendamentos=agendamentos,
        inicio=inicio,
        fim=fim
    )

    pdf = BytesIO()
    pisa.CreatePDF(html, dest=pdf)
    pdf.seek(0)
    response = make_response(pdf.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=faturamento_por_cliente.pdf'
    return response


# ---------------- RELATÓRIO POR SERVIÇO ---------------- #
@app.route('/relatorio/faturamento/por-servico/pdf')
@login_required
def relatorio_faturamento_por_servico_pdf():
    data_inicio = request.args.get('data_inicio')
    data_fim = request.args.get('data_fim')
    hoje = date.today()

    if not data_inicio or not data_fim:
        inicio = hoje - timedelta(days=30)
        fim = hoje
    else:
        inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        fim = datetime.strptime(data_fim, "%Y-%m-%d").date()

    query = db.session.query(
        Servico.nome,
        func.sum(Agendamento.valor_pago).label('total'),
        func.count(Agendamento.id).label('qtd')
    ).join(Servico, Servico.id == Agendamento.servico_id)\
     .filter(Agendamento.status.ilike('%concluido%'))\
     .filter(Agendamento.data.between(inicio, fim))

    # Usuário comum só vê os seus agendamentos
    if current_user.role != 'admin':
        query = query.filter(Agendamento.usuario_id == current_user.id)

    fatur_por_servico = query.group_by(Servico.nome)\
                             .order_by(func.sum(Agendamento.valor_pago).desc())\
                             .all()

    html = render_template(
        'relatorios/faturamento_por_servico_pdf.html',
        fatur_por_servico=fatur_por_servico,
        inicio=inicio,
        fim=fim
    )

    pdf = BytesIO()
    pisa.CreatePDF(html, dest=pdf)
    pdf.seek(0)
    response = make_response(pdf.read())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = 'inline; filename=faturamento_por_servico.pdf'
    return response
