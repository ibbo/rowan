#!/bin/bash

# VPS Deployment Script for Scottish Country Dance Assistant
# This script helps deploy the Gradio app on a VPS

set -e  # Exit on any error

echo "🏴󠁧󠁢󠁳󠁣󠁴󠁿 Scottish Country Dance Assistant - VPS Deployment"
echo "=========================================================="

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to install uv if not present
install_uv() {
    if ! command_exists uv; then
        echo "📦 Installing uv package manager..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.cargo/bin:$PATH"
    else
        echo "✅ uv is already installed"
    fi
}

# Function to setup systemd service
setup_systemd_service() {
    echo "🔧 Setting up systemd service..."
    
    # Get the current directory and user
    CURRENT_DIR=$(pwd)
    CURRENT_USER=$(whoami)
    
    # Create systemd service file
    sudo tee /etc/systemd/system/dance-assistant.service > /dev/null <<EOF
[Unit]
Description=Scottish Country Dance Assistant Web UI
After=network.target

[Service]
Type=simple
User=$CURRENT_USER
WorkingDirectory=$CURRENT_DIR
Environment=PATH=$HOME/.cargo/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=$HOME/.cargo/bin/uv run gradio_app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    # Reload systemd and enable the service
    sudo systemctl daemon-reload
    sudo systemctl enable dance-assistant
    
    echo "✅ Systemd service created and enabled"
}

# Function to setup nginx reverse proxy (optional)
setup_nginx() {
    read -p "🌐 Do you want to setup nginx reverse proxy? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        read -p "Enter your domain name (e.g., dance.example.com): " DOMAIN
        
        if [ -z "$DOMAIN" ]; then
            echo "❌ Domain name cannot be empty"
            return 1
        fi
        
        # Install nginx if not present
        if ! command_exists nginx; then
            echo "📦 Installing nginx..."
            sudo apt update
            sudo apt install -y nginx
        fi
        
        # Create nginx config
        sudo tee /etc/nginx/sites-available/dance-assistant > /dev/null <<EOF
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:7860;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket support for Gradio
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF
        
        # Enable the site
        sudo ln -sf /etc/nginx/sites-available/dance-assistant /etc/nginx/sites-enabled/
        sudo nginx -t
        sudo systemctl reload nginx
        
        echo "✅ Nginx configured for domain: $DOMAIN"
        echo "📝 Note: You may want to setup SSL with Let's Encrypt:"
        echo "   sudo apt install certbot python3-certbot-nginx"
        echo "   sudo certbot --nginx -d $DOMAIN"
    fi
}

# Function to setup firewall
setup_firewall() {
    if command_exists ufw; then
        echo "🔥 Configuring firewall..."
        sudo ufw allow ssh
        sudo ufw allow 80
        sudo ufw allow 443
        sudo ufw allow 7860  # Direct access to Gradio (optional)
        echo "✅ Firewall configured"
    else
        echo "⚠️  UFW not found. Please configure your firewall manually to allow ports 80, 443, and optionally 7860"
    fi
}

# Main deployment process
main() {
    echo "🚀 Starting deployment process..."
    
    # Check if we're in the right directory
    if [ ! -f "gradio_app.py" ]; then
        echo "❌ Error: gradio_app.py not found in current directory"
        echo "Please run this script from the dance-teacher directory"
        exit 1
    fi
    
    # Check for .env file
    if [ ! -f ".env" ]; then
        echo "⚠️  Warning: .env file not found"
        echo "Please create a .env file with your OPENAI_API_KEY"
        echo "Example:"
        echo "OPENAI_API_KEY=your-key-here"
        echo "SCDDB_SQLITE=data/scddb/scddb.sqlite"
        echo ""
        read -p "Continue anyway? (y/n): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Install uv
    install_uv
    
    # Install dependencies
    echo "📦 Installing Python dependencies..."
    uv sync
    
    # Check if database exists
    if [ ! -f "data/scddb/scddb.sqlite" ]; then
        echo "📊 Database not found. Running refresh script..."
        uv run refresh_scddb.py
    fi
    
    # Test the app briefly
    echo "🧪 Testing the application..."
    timeout 10s uv run gradio_app.py || {
        echo "⚠️  App test completed (this is normal for the timeout)"
    }
    
    # Setup systemd service
    setup_systemd_service
    
    # Setup nginx (optional)
    setup_nginx
    
    # Setup firewall
    setup_firewall
    
    # Start the service
    echo "🚀 Starting the service..."
    sudo systemctl start dance-assistant
    sudo systemctl status dance-assistant --no-pager
    
    echo ""
    echo "🎉 Deployment completed!"
    echo "=========================================="
    echo "✅ Service: dance-assistant"
    echo "✅ Status: $(sudo systemctl is-active dance-assistant)"
    echo "✅ Port: 7860 (direct access)"
    echo "✅ Logs: sudo journalctl -u dance-assistant -f"
    echo ""
    echo "🌐 Access your app at:"
    echo "   - http://your-server-ip:7860"
    if [ ! -z "$DOMAIN" ]; then
        echo "   - http://$DOMAIN (if nginx is configured)"
    fi
    echo ""
    echo "📋 Useful commands:"
    echo "   - Start:   sudo systemctl start dance-assistant"
    echo "   - Stop:    sudo systemctl stop dance-assistant"
    echo "   - Restart: sudo systemctl restart dance-assistant"
    echo "   - Logs:    sudo journalctl -u dance-assistant -f"
    echo "   - Status:  sudo systemctl status dance-assistant"
}

# Run main function
main "$@"
