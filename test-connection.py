from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/api/ping", methods=["GET"])
def ping():
    return jsonify({
        "status": "ok",
        "mensagem": "Backend online"
    }), 200

@app.route("/api/teste-esp", methods=["POST"])
def teste_esp():
    try:
        data = request.get_json(force=True)

        dispositivo_id = data.get("dispositivo_id", "desconhecido")
        evento = data.get("evento", "sem_evento")
        valor = data.get("valor", None)

        print("\n=== DADO RECEBIDO DO ESP ===")
        print(f"dispositivo_id: {dispositivo_id}")
        print(f"evento: {evento}")
        print(f"valor: {valor}")
        print("============================\n")

        return jsonify({
            "status": "ok",
            "mensagem": "Dados recebidos com sucesso",
            "comando": "ligar_led",
            "recebido_de": dispositivo_id
        }), 200

    except Exception as e:
        return jsonify({
            "status": "erro",
            "mensagem": str(e)
        }), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)