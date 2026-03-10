const isMobile = window.innerWidth <= 768;
const CONFIG = {
    particleCount: isMobile ? 50 : 250,
    connectionDist: isMobile ? 100 : 150,
    mouseDist: isMobile ? 80 : 180,
    baseSpeed: 0.8,
    glow: true,
    trail: true
};
const canvas = document.getElementById('canvas1');
const ctx = canvas.getContext('2d');
let w, h;
let particlesArray = [];
let mouse = {
    x: null,
    y: null,
    radius: CONFIG.mouseDist
}
function updateConfig() {
    const isMobileNow = window.innerWidth <= 768;
    CONFIG.particleCount = isMobileNow ? 80 : 250;
    CONFIG.mouseDist = isMobileNow ? 80 : 180;
    CONFIG.connectionDist = isMobileNow ? 100 : 150;
    mouse.radius = CONFIG.mouseDist;
}
window.addEventListener('resize', function() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
    updateConfig();
    init();
});
window.addEventListener('mousemove', function(event) {
    mouse.x = event.x;
    mouse.y = event.y;
});
window.addEventListener('touchmove', function(event) {
    if (event.touches.length > 0) {
        mouse.x = event.touches[0].clientX;
        mouse.y = event.touches[0].clientY;
        event.preventDefault();
    }
});
window.addEventListener('mouseout', function() {
    mouse.x = undefined;
    mouse.y = undefined;
});
window.addEventListener('touchend', function() {
    mouse.x = undefined;
    mouse.y = undefined;
});
class Particle {
    constructor() {
        this.x = Math.random() * w;
        this.y = Math.random() * h;
        this.dx = (Math.random() - 0.5) * CONFIG.baseSpeed * 2;
        this.dy = (Math.random() - 0.5) * CONFIG.baseSpeed * 2;
        this.size = (Math.random() * 2) + 1;
        this.hue = Math.random() * 360;
    }
    draw() {
        ctx.beginPath();
        ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2, false);
        ctx.fillStyle = `hsl(${this.hue}, 100%, 60%)`;
        ctx.fill();
    }
    update() {
        if (this.x > w || this.x < 0) {
            this.dx = -this.dx;
        }
        if (this.y > h || this.y < 0) {
            this.dy = -this.dy;
        }

        let dx = mouse.x - this.x;
        let dy = mouse.y - this.y;
        let distance = Math.sqrt(dx*dx + dy*dy);

        if (mouse.x && mouse.y && distance < mouse.radius) {
            const forceDirectionX = dx / distance;
            const forceDirectionY = dy / distance;
            const maxDistance = mouse.radius;

            const force = (maxDistance - distance) / maxDistance;
            const directionX = forceDirectionX * force * 3;
            const directionY = forceDirectionY * force * 3;

            this.x -= directionX;
            this.y -= directionY;
        } else {
            if (this.x !== this.x + this.dx) {
                this.x += this.dx;
                this.y += this.dy;
            }
        }

        this.hue += 0.5;

        this.draw();
    }
}

function init() {
    w = canvas.width = window.innerWidth;
    h = canvas.height = window.innerHeight;
    particlesArray = [];
    for (let i = 0; i < CONFIG.particleCount; i++) {
        particlesArray.push(new Particle());
    }
}

function connect() {
    let opacityValue = 1;
    for (let a = 0; a < particlesArray.length; a++) {
        for (let b = a; b < particlesArray.length; b++) {
            let distance = ((particlesArray[a].x - particlesArray[b].x) * (particlesArray[a].x - particlesArray[b].x))
                                 + ((particlesArray[a].y - particlesArray[b].y) * (particlesArray[a].y - particlesArray[b].y));

            if (distance < (CONFIG.connectionDist * CONFIG.connectionDist)) {

                opacityValue = 1 - (distance / 20000);
                ctx.beginPath();
                ctx.lineWidth = 0.5;

                ctx.strokeStyle = `rgba(0, 255, 255, ${opacityValue})`;
                        
                ctx.moveTo(particlesArray[a].x, particlesArray[a].y);
                ctx.lineTo(particlesArray[b].x, particlesArray[b].y);
                ctx.stroke();
            }
        }
    }
}
function animate() {
    requestAnimationFrame(animate);
            
    if (CONFIG.trail) {
        ctx.fillStyle = 'rgba(5, 5, 5, 0.15)';
        ctx.fillRect(0, 0, w, h);
    } else {
        ctx.clearRect(0, 0, w, h);
    }

    if (CONFIG.glow) {
        ctx.globalCompositeOperation = 'lighter';
    }

    for (let i = 0; i < particlesArray.length; i++) {
        particlesArray[i].update();
    }
    connect();
            
    ctx.globalCompositeOperation = 'source-over';
}
updateConfig();
init();
animate();