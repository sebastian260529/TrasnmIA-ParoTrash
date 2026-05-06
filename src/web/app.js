let currentData = null;

function setStatus(msg) {
    document.getElementById('status-text').textContent = msg;
}

function addChatMessage(role, text) {
    const div = document.getElementById('chat-messages');
    const msg = document.createElement('div');
    msg.className = 'chat-msg ' + role;
    msg.textContent = text;
    div.appendChild(msg);
    div.scrollTop = div.scrollHeight;
}

function getNivelClass(nivel) {
    if (nivel === 'alto') return 'nivel-alto';
    if (nivel === 'medio') return 'nivel-medio';
    return 'nivel-bajo';
}

function getTipoDatoClass(tipo) {
    if (tipo === 'real' || tipo === 'real_hoy') return 'tipo-real';
    if (tipo === 'historico') return 'tipo-historico';
    if (tipo === 'mixto') return 'tipo-mixto';
    return 'tipo-sin-datos';
}

function renderResultado(data) {
    currentData = data;
    document.getElementById('results').style.display = 'block';

    const probEl = document.getElementById('prob-val');
    probEl.textContent = data.probabilidad + '%';
    probEl.className = 'big-num ' + getNivelClass(data.nivel_riesgo);

    const nivelEl = document.getElementById('nivel-val');
    nivelEl.textContent = data.nivel_riesgo.toUpperCase();
    nivelEl.className = 'big-num ' + getNivelClass(data.nivel_riesgo);

    const fuentes = data.fuentes || {};

    var buses = fuentes.buses || {};
    document.getElementById('score-buses').textContent = buses.score || 0;
    var tipoBuses = document.getElementById('tipo-buses');
    tipoBuses.textContent = buses.tipo_dato || '';
    tipoBuses.className = 'tipo-dato ' + getTipoDatoClass(buses.tipo_dato);
    if (buses.advertencia) {
        tipoBuses.textContent += ' - ' + buses.advertencia;
    }

    var whatsapp = fuentes.whatsapp_transmilenio || {};
    document.getElementById('score-whatsapp').textContent = whatsapp.score || 0;
    var tipoWapp = document.getElementById('tipo-whatsapp');
    tipoWapp.textContent = whatsapp.tipo_dato || '';
    tipoWapp.className = 'tipo-dato ' + getTipoDatoClass(whatsapp.tipo_dato);

    var wappBanner = document.getElementById('whatsapp-alert-banner');
    if (whatsapp.tipo_dato === 'real_hoy' && whatsapp.alerta_oficial_hoy) {
        wappBanner.style.display = 'block';
        wappBanner.innerHTML = '<strong>Alerta oficial de hoy detectada</strong>';
        if (whatsapp.alertas_recientes && whatsapp.alertas_recientes.length > 0) {
            var alertaTexto = whatsapp.alertas_recientes[0].texto || '';
            if (alertaTexto) {
                wappBanner.innerHTML += '<br><small>' + alertaTexto.substring(0, 200) + '</small>';
            }
        }
    } else {
        wappBanner.style.display = 'none';
    }

    var alertaOficialDiv = document.getElementById('alerta-oficial-section');
    if (data.alerta_oficial_hoy) {
        alertaOficialDiv.style.display = 'block';
    } else {
        alertaOficialDiv.style.display = 'none';
    }

    var firebase = fuentes.firebase_reportes || {};
    document.getElementById('score-firebase').textContent = firebase.score || 0;
    var tipoFb = document.getElementById('tipo-firebase');
    tipoFb.textContent = firebase.tipo_dato || '';
    tipoFb.className = 'tipo-dato ' + getTipoDatoClass(firebase.tipo_dato);

    var ia = fuentes.ia_texto || {};
    document.getElementById('score-ia').textContent = ia.score || 0;
    var tipoIa = document.getElementById('tipo-ia');
    tipoIa.textContent = ia.tipo_dato || '';
    tipoIa.className = 'tipo-dato ' + getTipoDatoClass(ia.tipo_dato);

    var geo = fuentes.geolocalizacion || {};
    document.getElementById('score-geo').textContent = geo.score || 0;
    var tipoGeo = document.getElementById('tipo-geo');
    tipoGeo.textContent = geo.tipo_dato || '';
    tipoGeo.className = 'tipo-dato ' + getTipoDatoClass(geo.tipo_dato);

    const explDiv = document.getElementById('explicacion-content');
    explDiv.innerHTML = '';
    (data.explicacion || []).forEach(function(e) {
        const p = document.createElement('p');
        p.textContent = e;
        explDiv.appendChild(p);
    });

    const recDiv = document.getElementById('recomendaciones-content');
    recDiv.innerHTML = '';
    (data.recomendaciones || []).forEach(function(r) {
        const li = document.createElement('li');
        li.textContent = r;
        recDiv.appendChild(li);
    });

    const fUsadasDiv = document.getElementById('fuentes-content');
    fUsadasDiv.innerHTML = '';
    var fuentesUsadas = data.fuentes_usadas || [];
    if (fuentesUsadas.length > 0) {
        fuentesUsadas.forEach(function(name) {
            var span = document.createElement('span');
            span.className = 'tag tag-usada';
            span.textContent = name;
            fUsadasDiv.appendChild(span);
        });
    } else {
        fUsadasDiv.innerHTML = '<p class="text-muted">Ninguna fuente con datos disponibles.</p>';
    }

    const fNoDispDiv = document.getElementById('fuentes-no-disp-content');
    fNoDispDiv.innerHTML = '';
    var fuentesNoDisp = data.fuentes_no_disponibles || [];
    if (fuentesNoDisp.length > 0) {
        fuentesNoDisp.forEach(function(name) {
            var span = document.createElement('span');
            span.className = 'tag tag-no-disp';
            span.textContent = name;
            fNoDispDiv.appendChild(span);
        });
        fNoDispDiv.innerHTML += '<p class="text-muted">Estos modulos no tienen datos reales en este momento.</p>';
    } else {
        fNoDispDiv.innerHTML = '<p class="text-muted">Todas las fuentes tienen datos disponibles.</p>';
    }

    const fDiv = document.getElementById('fuentes-section');
    Object.keys(fuentes).forEach(function(key) {
        var f = fuentes[key];
        var div = document.createElement('div');
        div.style.marginBottom = '0.6rem';
        div.style.padding = '0.5rem';
        div.style.background = '#0f172a';
        div.style.borderRadius = '6px';
        var html = '<strong>' + key + ':</strong> score=' + (f.score || 0) +
            ' | tipo=' + (f.tipo_dato || 'N/A') +
            ' | ' + (f.detalle || '');
        if (f.cantidad !== undefined) {
            html += ' | cantidad=' + f.cantidad;
        }
        if (f.coincidencias !== undefined) {
            html += ' | coincidencias=' + f.coincidencias;
        }
        if (f.advertencia) {
            html += '<br><span class="warning">' + f.advertencia + '</span>';
        }
        div.innerHTML = html;
    });

    const ubi = data.ubicacion_inteligente;
    const ubiDiv = document.getElementById('ubicacion-content');
    if (ubi) {
        ubiDiv.innerHTML = '<p>Zona: <strong>' + ubi.zona_consultada + '</strong> | Dir: ' + (ubi.direccion_normalizada || 'N/A') +
            ' | Buses cercanos: ' + (ubi.buses_cercanos || 0) +
            ' | Reportes cercanos: ' + (ubi.reportes_cercanos || 0) +
            ' | Alertas historicas: ' + (ubi.alertas_historicas_cercanas || 0) + '</p>';
        if (ubi.coordenadas_estimadas && ubi.coordenadas_estimadas.lat !== null) {
            ubiDiv.innerHTML += '<p>Coordenadas: (' + ubi.coordenadas_estimadas.lat + ', ' + ubi.coordenadas_estimadas.lon + ')</p>';
        }
    }

    document.getElementById('debug-json').textContent = JSON.stringify(data, null, 2);
}

async function analizarRiesgo() {
    const zona = document.getElementById('zona').value.trim();
    if (!zona) { setStatus('Escribe una zona primero'); return; }
    setStatus('Analizando con datos reales...');
    try {
        const resp = await fetch('/prediccion/integrada?zona=' + encodeURIComponent(zona));
        const data = await resp.json();
        renderResultado(data);
        setStatus('Analisis completado para ' + zona + ' (modo: ' + (data.modo_operacion || 'real') + ')');
        return data;
    } catch (e) {
        setStatus('Error: ' + e.message);
        addChatMessage('bot', 'Error al analizar: ' + e.message);
    }
}

async function enviarChatbot() {
    const pregunta = document.getElementById('chat-input').value.trim();
    const zona = document.getElementById('zona').value.trim();
    if (!pregunta) return;
    addChatMessage('user', pregunta);
    document.getElementById('chat-input').value = '';
    setStatus('Consultando chatbot...');
    try {
        const resp = await fetch('/chatbot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pregunta: pregunta, zona: zona })
        });
        const data = await resp.json();
        addChatMessage('bot', data.respuesta || 'Sin respuesta');
        renderResultado(data);
        setStatus('Listo');
    } catch (e) {
        addChatMessage('bot', 'Error: ' + e.message);
        setStatus('Error: ' + e.message);
    }
}

async function cargarEstadoFuentes() {
    try {
        const resp = await fetch('/fuentes/estado');
        const estado = await resp.json();
        const div = document.getElementById('fuentes-status-content');
        div.innerHTML = '';
        const fuentes = [
            { key: 'buses', label: 'Buses / Anomalias' },
            { key: 'whatsapp_transmilenio', label: 'WhatsApp / TransMilenio' },
            { key: 'firebase', label: 'Firebase / Reportes' },
            { key: 'ia_texto', label: 'IA / Texto' },
            { key: 'geolocalizacion', label: 'Geolocalizacion' }
        ];
        fuentes.forEach(function(f) {
            var info = estado[f.key] || {};
            var row = document.createElement('div');
            row.className = 'fuente-status-row';
            var dotClass = info.disponible ? 'dot-ok' : 'dot-err';
            var dot = '<span class="fuente-dot ' + dotClass + '"></span>';
            var detalles = (info.detalle || '') + (info.modo ? ' [' + info.modo + ']' : '') +
                (info.registros ? ' (' + info.registros + ' registros)' : '');
            row.innerHTML = dot + ' <strong>' + f.label + ':</strong> ' + detalles;
            div.appendChild(row);
        });
    } catch (e) {
        document.getElementById('fuentes-status-content').innerHTML =
            '<span class="error">Error al cargar estado: ' + e.message + '</span>';
    }
}

document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('btn-analizar').addEventListener('click', analizarRiesgo);
    document.getElementById('btn-chatbot').addEventListener('click', enviarChatbot);
    document.getElementById('chat-input').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') enviarChatbot();
    });
    cargarEstadoFuentes();
    setStatus('Listo - Escribe una zona y analiza el riesgo con datos reales');
    addChatMessage('bot', 'Bienvenido a TransmIA ParoTrash. El sistema usa datos reales disponibles: buses, historico TransMilenio, reportes Firebase (si configurado), analisis de texto y geolocalizacion. Escribe una zona y haz clic en "Analizar riesgo".');
});
