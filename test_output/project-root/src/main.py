from .app import app

def run_server():
    return app

def main():
    with open('../configs/settings.yaml', 'r') as f:
        settings = yaml.safe_load(f)
    app.run(host=settings['host'], port=settings['port'], debug=settings['debug'])

if __name__ == '__main__':
    main()
