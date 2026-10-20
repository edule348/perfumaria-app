from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'perfumaria_secret_key'

DB_NAME = 'perfumaria.db'

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    if not os.path.exists(DB_NAME):
        conn = get_db()
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                telefone TEXT NOT NULL,
                aniversario TEXT
            );
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codigo TEXT UNIQUE NOT NULL,
                descricao TEXT NOT NULL,
                valor_compra REAL NOT NULL,
                valor_venda REAL NOT NULL,
                foto TEXT
            );
            CREATE TABLE IF NOT EXISTS pedidos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cliente_id INTEGER,
                data_pedido TEXT NOT NULL,
                qtd_parcelas INTEGER NOT NULL,
                valor_total REAL NOT NULL,
                valor_pago REAL DEFAULT 0,
                FOREIGN KEY(cliente_id) REFERENCES clientes(id)
            );
            CREATE TABLE IF NOT EXISTS itens_pedido (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER,
                produto_id INTEGER,
                quantidade INTEGER NOT NULL,
                valor_unitario REAL NOT NULL,
                valor_total REAL NOT NULL,
                FOREIGN KEY(pedido_id) REFERENCES pedidos(id),
                FOREIGN KEY(produto_id) REFERENCES produtos(id)
            );
            CREATE TABLE IF NOT EXISTS parcelas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pedido_id INTEGER,
                numero_parcela INTEGER NOT NULL,
                vencimento TEXT NOT NULL,
                valor_parcela REAL NOT NULL,
                status TEXT DEFAULT 'Pendente',
                FOREIGN KEY(pedido_id) REFERENCES pedidos(id)
            );
        ''')
        conn.commit()
        conn.close()

init_db()

@app.route('/')
def index():
    conn = get_db()
    pedidos = conn.execute('''
        SELECT p.*, c.nome as cliente_nome, c.telefone as cliente_tel 
        FROM pedidos p 
        JOIN clientes c ON p.cliente_id = c.id 
        ORDER BY p.id DESC
    ''').fetchall()
    conn.close()
    return render_template('index.html', pedidos=pedidos)

@app.route('/produtos', methods=['GET', 'POST'])
def produtos():
    conn = get_db()
    if request.method == 'POST':
        codigo = request.form['codigo']
        descricao = request.form['descricao']
        valor_compra = float(request.form['valor_compra'])
        valor_venda = float(request.form['valor_venda'])
        foto = request.form.get('foto', '')
        
        conn.execute('INSERT INTO produtos (codigo, descricao, valor_compra, valor_venda, foto) VALUES (?, ?, ?, ?, ?)',
                     (codigo, descricao, valor_compra, valor_venda, foto))
        conn.commit()
        flash('Produto cadastrado com sucesso!', 'success')
        return redirect(url_for('produtos'))
        
    produtos = conn.execute('SELECT * FROM produtos').fetchall()
    conn.close()
    return render_template('produtos.html', produtos=produtos)

@app.route('/clientes', methods=['GET', 'POST'])
def clientes():
    conn = get_db()
    if request.method == 'POST':
        nome = request.form['nome']
        telefone = request.form['telefone']
        aniversario = request.form.get('aniversario', '')
        conn.execute('INSERT INTO clientes (nome, telefone, aniversario) VALUES (?, ?, ?)',
                     (nome, telefone, aniversario))
        conn.commit()
        flash('Cliente cadastrado com sucesso!', 'success')
        return redirect(url_for('clientes'))
        
    clientes = conn.execute('SELECT * FROM clientes').fetchall()
    conn.close()
    return render_template('clientes.html', clientes=clientes)

@app.route('/cliente/<int:cliente_id>')
def cliente_detalhe(cliente_id):
    conn = get_db()
    cliente = conn.execute('SELECT * FROM clientes WHERE id = ?', (cliente_id,)).fetchone()
    pedidos = conn.execute('SELECT * FROM pedidos WHERE cliente_id = ? ORDER BY data_pedido DESC', (cliente_id,)).fetchall()
    
    historico_pedidos = []
    for ped in pedidos:
        itens = conn.execute('''
            SELECT ip.*, pr.descricao, pr.codigo FROM itens_pedido ip 
            JOIN produtos pr ON ip.produto_id = pr.id 
            WHERE ip.pedido_id = ?
        ''', (ped['id'],)).fetchall()
        parcelas = conn.execute('SELECT * FROM parcelas WHERE pedido_id = ?', (ped['id'],)).fetchall()
        historico_pedidos.append({'pedido': ped, 'itens': itens, 'parcelas': parcelas})
        
    conn.close()
    return render_template('cliente_detalhe.html', cliente=cliente, historico=historico_pedidos)

@app.route('/pedido/novo', methods=['GET', 'POST'])
def novo_pedido():
    conn = get_db()
    if request.method == 'POST':
        cliente_id = request.form['cliente_id']
        data_pedido = request.form['data_pedido']
        qtd_parcelas = int(request.form['qtd_parcelas'])
        produto_id = int(request.form['produto_id'])
        quantidade = int(request.form['quantidade'])
        valor_unitario = float(request.form['valor_unitario'])
        valor_total = valor_unitario * quantidade
        
        cursor = conn.cursor()
        cursor.execute('INSERT INTO pedidos (cliente_id, data_pedido, qtd_parcelas, valor_total, valor_pago) VALUES (?, ?, ?, ?, 0)',
                       (cliente_id, data_pedido, qtd_parcelas, valor_total))
        pedido_id = cursor.lastrowid
        
        cursor.execute('INSERT INTO itens_pedido (pedido_id, produto_id, quantidade, valor_unitario, valor_total) VALUES (?, ?, ?, ?, ?)',
                       (pedido_id, produto_id, quantidade, valor_unitario, valor_total))
        
        valor_parcela = valor_total / qtd_parcelas
        dt = datetime.strptime(data_pedido, '%Y-%m-%d')
        for i in range(1, qtd_parcelas + 1):
            if dt.month + i > 12:
                m = (dt.month + i) % 12
                y = dt.year + ((dt.month + i - 1) // 12)
            else:
                m = dt.month + i
                y = dt.year
            vencimento = f"{y:04d}-{m:02d}-05"
            cursor.execute('INSERT INTO parcelas (pedido_id, numero_parcela, vencimento, valor_parcela, status) VALUES (?, ?, ?, ?, ?)',
                           (pedido_id, i, vencimento, valor_parcela, 'Pendente'))
                           
        conn.commit()
        conn.close()
        flash('Pedido criado com sucesso!', 'success')
        return redirect(url_for('index'))
        
    clientes = conn.execute('SELECT * FROM clientes').fetchall()
    produtos = conn.execute('SELECT * FROM produtos').fetchall()
    conn.close()
    return render_template('novo_pedido.html', clientes=clientes, produtos=produtos)

@app.route('/pedido/<int:pedido_id>/orcamento')
def orcamento(pedido_id):
    conn = get_db()
    pedido = conn.execute('''
        SELECT p.*, c.nome as cliente_nome, c.telefone as cliente_tel 
        FROM pedidos p JOIN clientes c ON p.cliente_id = c.id 
        WHERE p.id = ?
    ''', (pedido_id,)).fetchone()
    
    itens = conn.execute('''
        SELECT ip.*, pr.descricao, pr.codigo, pr.foto FROM itens_pedido ip 
        JOIN produtos pr ON ip.produto_id = pr.id 
        WHERE ip.pedido_id = ?
    ''', (pedido_id,)).fetchall()
    
    parcelas = conn.execute('SELECT * FROM parcelas WHERE pedido_id = ?', (pedido_id,)).fetchall()
    conn.close()
    
    pix_chave = "030.127.480-08"
    return render_template('orcamento.html', pedido=pedido, itens=itens, parcelas=parcelas, pix_chave=pix_chave)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
