from flask import Flask, request, jsonify
from datetime import datetime
import mysql.connector
from dotenv import load_dotenv
import os

load_dotenv()
app = Flask(__name__)

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "database": os.getenv("DB_NAME")
}


def get_conn():
    return mysql.connector.connect(**DB_CONFIG)

def parse_dt(texto):
    if texto is None:
        return None
    return datetime.fromisoformat(texto)

@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({"status": "ok", "mensagem": "Backend online"}), 200

@app.route("/api/sessoes/sincronizar", methods=["POST"])
def sincronizar_sessao():
    conn = None
    cursor = None

    try:
        data = request.get_json(force=True)

        sessao_local = data.get("sessao_local")
        identificador_dispositivo = data.get("identificador_dispositivo")
        tipo_evento = data.get("tipo_evento", "aula")
        forma_inicio = data.get("forma_inicio", "gatilho_porta")
        confirmado_por_rfid = 1 if data.get("confirmado_por_rfid", True) else 0
        descricao = data.get("descricao")
        inicio = parse_dt(data.get("inicio"))
        fim = parse_dt(data.get("fim"))
        host_tag = data.get("host_tag")
        presencas = data.get("presencas", [])

        if not sessao_local or not identificador_dispositivo or not host_tag:
            return jsonify({
                "status": "erro",
                "mensagem": "Campos obrigatorios ausentes"
            }), 400

        conn = get_conn()
        conn.start_transaction()
        cursor = conn.cursor(dictionary=True)

        # 1. Evita duplicacao
        cursor.execute("""
            SELECT evento_id
            FROM sincronizacoes_sessao
            WHERE sessao_local = %s
        """, (sessao_local,))
        ja_sync = cursor.fetchone()

        if ja_sync:
            conn.rollback()
            return jsonify({
                "status": "ok",
                "mensagem": "Sessao ja sincronizada anteriormente",
                "evento_id": ja_sync["evento_id"],
                "duplicado": True
            }), 200

        # 2. Resolve dispositivo e sala
        cursor.execute("""
            SELECT id_dispositivo, sala_id
            FROM dispositivos
            WHERE identificador_fisico = %s
              AND ativo = 1
        """, (identificador_dispositivo,))
        dispositivo = cursor.fetchone()

        if not dispositivo:
            conn.rollback()
            return jsonify({
                "status": "erro",
                "mensagem": f"Dispositivo nao encontrado: {identificador_dispositivo}"
            }), 404

        dispositivo_id = dispositivo["id_dispositivo"]
        sala_id = dispositivo["sala_id"]

        # 3. Resolve host
        cursor.execute("""
            SELECT rt.usuario_id
            FROM rfid_tags rt
            WHERE rt.codigo = %s
              AND rt.ativa = 1
        """, (host_tag,))
        host = cursor.fetchone()

        if not host:
            conn.rollback()
            return jsonify({
                "status": "erro",
                "mensagem": f"Host nao encontrado para a tag: {host_tag}"
            }), 404

        host_id = host["usuario_id"]

        # 4. Cria evento
        cursor.execute("""
            INSERT INTO eventos (
                tipo,
                host,
                autorizado_por,
                forma_inicio,
                confirmado_por_rfid,
                sala_id,
                status,
                descricao,
                inicio_real,
                fim_real
            ) VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s, %s)
        """, (
            tipo_evento,
            host_id,
            forma_inicio,
            confirmado_por_rfid,
            sala_id,
            "finalizado",
            f"{descricao or ''} [sessao_local={sessao_local}]",
            inicio,
            fim
        ))
        evento_id = cursor.lastrowid

        # 5. Registra host como participante
        cursor.execute("""
            INSERT IGNORE INTO evento_participantes (evento_id, usuario_id, papel)
            VALUES (%s, %s, %s)
        """, (evento_id, host_id, "professor"))

        # 6. Presencas
        total_participantes = 0
        total_linhas_presenca = 0

        for item in presencas:
            tag = item.get("tag")
            papel = item.get("papel", "aluno")
            entrada = parse_dt(item.get("entrada"))
            saida = parse_dt(item.get("saida"))

            if not tag:
                continue

            cursor.execute("""
                SELECT rt.usuario_id
                FROM rfid_tags rt
                WHERE rt.codigo = %s
                  AND rt.ativa = 1
            """, (tag,))
            usuario = cursor.fetchone()

            if not usuario:
                continue

            usuario_id = usuario["usuario_id"]

            cursor.execute("""
                INSERT IGNORE INTO evento_participantes (evento_id, usuario_id, papel)
                VALUES (%s, %s, %s)
            """, (evento_id, usuario_id, papel))

            total_participantes += 1

            if entrada:
                cursor.execute("""
                    INSERT INTO presencas (
                        id_evento,
                        id_usuario,
                        dispositivo_id,
                        data_hora,
                        tipo,
                        origem,
                        valido
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    evento_id,
                    usuario_id,
                    dispositivo_id,
                    entrada,
                    "entrada",
                    "sincronizacao_dispositivo",
                    1
                ))
                total_linhas_presenca += 1

            if saida:
                cursor.execute("""
                    INSERT INTO presencas (
                        id_evento,
                        id_usuario,
                        dispositivo_id,
                        data_hora,
                        tipo,
                        origem,
                        valido
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    evento_id,
                    usuario_id,
                    dispositivo_id,
                    saida,
                    "saida",
                    "sincronizacao_dispositivo",
                    1
                ))
                total_linhas_presenca += 1

        # 7. Marca sincronizacao
        cursor.execute("""
            INSERT INTO sincronizacoes_sessao (sessao_local, evento_id)
            VALUES (%s, %s)
        """, (sessao_local, evento_id))

        conn.commit()

        return jsonify({
            "status": "ok",
            "mensagem": "Sessao sincronizada com sucesso",
            "evento_id": evento_id,
            "participantes_processados": total_participantes,
            "linhas_presenca": total_linhas_presenca
        }), 201

    except Exception as e:
        if conn:
            conn.rollback()
        return jsonify({
            "status": "erro",
            "mensagem": str(e)
        }), 500

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)