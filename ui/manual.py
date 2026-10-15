"""
ui/manual.py — Manual de ayuda en español argentino.
"""

MANUAL_HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  body {
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
    color: #1e293b;
    background: #ffffff;
    margin: 0; padding: 16px;
    line-height: 1.6;
  }
  h1 { font-size: 20px; color: #0f172a; border-bottom: 2px solid #3b82f6; padding-bottom: 8px; }
  h2 { font-size: 15px; color: #1e293b; margin-top: 20px; margin-bottom: 6px; }
  h3 { font-size: 13px; color: #3b82f6; margin-top: 12px; margin-bottom: 4px; }
  h4 { font-size: 13px; color: #0f172a; margin-top: 10px; margin-bottom: 2px; }
  p  { margin: 6px 0; }
  ol, ul { margin: 6px 0; padding-left: 20px; }
  li { margin: 4px 0; }
  .tip  { background: #eff6ff; border-left: 3px solid #3b82f6; padding: 8px 12px; border-radius: 0 6px 6px 0; margin: 8px 0; }
  .warn { background: #fffbeb; border-left: 3px solid #f59e0b; padding: 8px 12px; border-radius: 0 6px 6px 0; margin: 8px 0; }
  code { background: #f1f5f9; padding: 2px 5px; border-radius: 3px; font-family: monospace; font-size: 12px; }
  table { border-collapse: collapse; width: 100%; margin: 8px 0; }
  th { background: #f1f5f9; padding: 6px 10px; text-align: left; font-weight: 700; border: 1px solid #e2e8f0; }
  td { padding: 5px 10px; border: 1px solid #e2e8f0; }
  tr:nth-child(even) td { background: #f8fafc; }
  .section-sep { border: none; border-top: 1px solid #e2e8f0; margin: 20px 0; }
</style>
</head>
<body>

<h1>📖 Manual de Universal Converter</h1>

<!-- ─── 1 ─── -->
<h2>1. ¿Qué hace esta aplicación?</h2>
<p>
Convierte archivos de un formato a otro —fotos JPG a PDF, Word a texto plano,
videos MP4 a MP3— y además trae herramientas para trabajar con documentos:
unir, partir, firmar digitalmente, reconocer texto de escaneos y sacar la
huella digital (hash) de cualquier archivo.
</p>

<h3>Si no sabés por dónde empezar, empezá acá</h3>
<p>
No hace falta que adivines qué herramienta usar. En <strong>🏠 Inicio</strong>, arriba
de todo, está la lista <strong>«¿Qué necesitás hacer?»</strong>: cada renglón es un
problema escrito como uno lo diría —<em>«Un PDF pesa demasiado y no me deja
subirlo»</em>, <em>«Necesito la foto del momento exacto de un video de cámara»</em>—
y a la derecha dice a qué botón ir.
</p>
<p>
<strong>Tocá el renglón y el programa te lleva solo</strong>: no solo al módulo, sino
a la solapa exacta de adentro. Si la lista te resulta larga, escribí una palabra en el
buscador de arriba a la derecha (<em>pdf</em>, <em>firmar</em>, <em>video</em>,
<em>pesa</em>) y la lista se achica a lo que coincide.
</p>

<h3>Dónde está cada cosa</h3>
<p>
Después, cuando le tomes la mano, todo se maneja desde la <strong>barra lateral
izquierda</strong>. Los botones están agrupados por preguntas: <strong>¿lo necesitás en
otro formato?</strong> (Convertir), <strong>¿trabajar sobre el archivo?</strong> (PDF,
audio, video, tablas), <strong>¿escribir algo?</strong> y <strong>¿comprobar que no se
tocó?</strong> (el hash). Si dejás el mouse quieto sobre cualquier botón, aparece un
cartelito que explica para qué sirve y qué hay adentro.
Dentro de cada módulo hay solapas:
</p>
<table>
  <tr><th>Módulo</th><th>Qué encontrás adentro</th></tr>
  <tr><td>🔄 Convertir</td><td>Cambiar el formato de cualquier archivo. Acá también está el OCR cuando además querés cambiar de formato.</td></tr>
  <tr><td>📄 PDF</td><td>Unir · Partir · Hojas dobles · Ajustar tamaño · Organizar páginas · Firmar · Reconocer texto (OCR) · Pasar a Excel la tabla de un PDF · Herramientas (comprimir, proteger, reparar).</td></tr>
  <tr><td>🎵 Audio</td><td>Cortar audio en partes · Unir varios audios · Mejorar audio (sacar ruido, realzar la voz) · Transcribir lo que se dice.</td></tr>
  <tr><td>🎬 Video</td><td>Partir video en partes · Ajustar tamaño · Mapa del video · Capturar el fotograma exacto de una grabación · Mejorar audio · Transcribir.</td></tr>
  <tr><td>📊 Tablas / Excel</td><td>Unir planillas XLS/XLSX y partir el resultado.</td></tr>
  <tr><td>✍️ Escribir</td><td>Redactar un texto acá mismo y guardarlo como MD, TXT, PDF, Word, OpenDocument, HTML o EPUB.</td></tr>
  <tr><td>🔢 Extraer hash</td><td>Sacar la huella digital de cualquier archivo y verificar que no fue modificado.</td></tr>
  <tr><td>📋 Log</td><td>Registro técnico y constancias de lo que hiciste.</td></tr>
  <tr><td>❓ Ayuda</td><td>Este manual.</td></tr>
</table>
<div class="tip">
  ✅ Funciona sin internet. Tus archivos nunca salen de tu computadora, y los
  originales nunca se modifican: siempre se genera una copia nueva.
</div>
<div class="tip">
  💡 Para cerrar el programa, usá el botón <strong>⏻</strong> de abajo a la izquierda,
  o la X de la ventana. Te va a pedir confirmación.
</div>

<hr class="section-sep">

<!-- ─── 2 ─── -->
<h2>2. ¿Cómo convierto un archivo?</h2>
<ol>
  <li><strong>Agregá los archivos:</strong> Arrastrá los archivos al área punteada, o usá el botón <em>"📄 Archivos"</em>. También podés arrastrar una carpeta entera.</li>
  <li><strong>Elegí el formato de salida:</strong> Usá el selector de formato de la derecha. Solo aparecen los formatos posibles para tus archivos.</li>
  <li><strong>Elegí la carpeta de destino:</strong> Por defecto se crea una carpeta
      <em>"PROCESADO CON NAVAJA"</em> junto a tus archivos. Es la misma en todo
      el programa, así siempre sabés dónde quedó lo que hiciste.</li>
  <li><strong>Configurá las opciones</strong> (opcional): marca de agua, leyenda, filtro de audio, etc.</li>
  <li><strong>Hacé clic en "🚀 CONVERTIR".</strong></li>
  <li>Cuando termine, hacé clic en <em>"📂 Abrir carpeta"</em> para ver los resultados.</li>
</ol>
<div class="warn">
  ⚠️ No cerrés el programa mientras convierte. Si necesitás parar, usá el botón <em>"🗑 Limpiar todo"</em>.
</div>

<hr class="section-sep">

<!-- ─── 3 ─── -->
<h2>3. ¿Qué es un "formato"?</h2>
<p>
Un formato es como el idioma en que está guardado un archivo.
Un archivo <code>.jpg</code> es una foto comprimida, un <code>.pdf</code>
es un documento que se ve igual en todas las computadoras,
un <code>.mp3</code> es música comprimida.
</p>
<p>
Cuando convertís, la información se traduce de un formato a otro.
Algunos formatos guardan más calidad pero ocupan más espacio (WAV, PNG, TIFF),
otros ocupan menos pero pierden algo de calidad (MP3, JPG, WEBP).
</p>

<hr class="section-sep">

<!-- ─── 4 ─── -->
<h2>4. 📷 Imágenes</h2>
<table>
  <tr><th>Formato</th><th>Para qué sirve</th></tr>
  <tr><td>JPG / JPEG</td><td>Fotos. Ocupa poco espacio. Ideal para compartir por correo o WhatsApp.</td></tr>
  <tr><td>PNG</td><td>Imágenes con fondo transparente, capturas de pantalla, gráficos.</td></tr>
  <tr><td>WEBP</td><td>Como JPG pero más liviano. Ideal para páginas web.</td></tr>
  <tr><td>BMP</td><td>Imagen sin comprimir, alta calidad pero ocupa mucho espacio.</td></tr>
  <tr><td>TIFF</td><td>Fotos de alta resolución para impresión profesional.</td></tr>
  <tr><td>GIF</td><td>Imágenes animadas simples. Se usa mucho en internet.</td></tr>
  <tr><td>SVG</td><td>Gráficos que no pierden calidad al agrandarlos (logos, iconos).</td></tr>
  <tr><td>ICO</td><td>Ícono de programa. Se usa para los íconos de Windows.</td></tr>
  <tr><td>PDF</td><td>Convierte una imagen en documento de una página.</td></tr>
  <tr><td>HEIC</td><td>Fotos tomadas con iPhone. Alta calidad y poco espacio.</td></tr>
</table>

<hr class="section-sep">

<!-- ─── 5 ─── -->
<h2>5. 🎵 Audio</h2>
<table>
  <tr><th>Formato</th><th>Para qué sirve</th></tr>
  <tr><td>MP3</td><td>El más compatible. Funciona en todos los dispositivos.</td></tr>
  <tr><td>WAV</td><td>Audio sin comprimir. Alta calidad, archivo grande.</td></tr>
  <tr><td>FLAC</td><td>Alta calidad sin pérdida pero con compresión.</td></tr>
  <tr><td>OGG</td><td>Formato libre y abierto. Buena calidad.</td></tr>
  <tr><td>OPUS</td><td>Ideal para grabaciones de voz y videollamadas.</td></tr>
  <tr><td>M4A</td><td>Audio de Apple. Buena calidad y compatible con iPhone.</td></tr>
  <tr><td>AAC</td><td>Similar a MP3 pero mejor calidad al mismo tamaño.</td></tr>
</table>
<h3>✂️ Cómo cortar un audio en partes</h3>
<ol>
  <li>Barra lateral → <strong>🎵 Audio</strong> → solapa <strong>"✂️ Cortar Audio"</strong>.</li>
  <li>Tocá <em>"🎵 Elegir audio"</em> y buscá el archivo.</li>
  <li>Elegí cómo cortarlo:
    <ul>
      <li><strong>"Por segundos"</strong> — cada parte dura lo que indiques. Para separar
          una audiencia larga en tramos parejos.</li>
      <li><strong>"Por kilobytes (KB)"</strong> — cada parte pesa como máximo lo que
          indiques. Para mandar por mail o subir a un sistema con límite.</li>
    </ul>
  </li>
  <li>Si querés, cambiá la carpeta de salida con <em>"Cambiar"</em>.</li>
  <li>Tocá <em>"✂️ Cortar audio"</em>. Al terminar,
      <em>"📂 Abrir carpeta de resultados"</em> te lleva a los archivos.</li>
</ol>

<h3>🔗 Cómo unir varios audios</h3>
<ol>
  <li>Barra lateral → <strong>🎵 Audio</strong> → solapa <strong>"🎵 Unir Audio"</strong>.</li>
  <li>Agregá los archivos y acomodá el orden: se pegan uno detrás de otro en el orden
      de la lista.</li>
  <li>Elegí dónde guardar y confirmá.</li>
</ol>

<h3>🔇 Filtro de ruido</h3>
<p>
El filtro se aplica <strong>durante una conversión</strong>, no en el módulo Audio.
En <strong>🔄 Convertir</strong>, cargá el audio y abrí la opción
<em>"🎚️ Aplicar filtro de audio"</em>. Ahí elegís:
</p>
<ul>
  <li><strong>Voz:</strong> Resalta la voz humana. Ideal para reuniones y entrevistas.</li>
  <li><strong>Agudos:</strong> Resalta los sonidos agudos como platillos.</li>
  <li><strong>Graves:</strong> Resalta el bajo y la profundidad del sonido.</li>
  <li><strong>Limpieza:</strong> Elimina el ruido de fondo (ventiladores, estática).</li>
</ul>
<div class="warn">
  ⚠️ El filtro <strong>modifica el sonido</strong>. Para material que vaya a usarse como
  prueba, conviene conservar también el archivo original sin filtrar.
</div>
<div class="tip">
  💡 Si querés <strong>escuchar cómo queda antes de guardar</strong> y regular cuánto
  se limpia, usá la solapa <strong>"🎚 Mejorar audio"</strong>, que se explica acá abajo.
</div>

<hr class="section-sep">

<!-- ─── 5b ─── -->
<h2>5b. 🎚 Mejorar el audio de una grabación</h2>
<p>
Para la grabación que se escucha mal: el micrófono de ambiente de una cámara Gesell,
una audiencia con el aire acondicionado de fondo, una persona que habla lejos y
bajito. La solapa tiene seis perillas, como un ecualizador, y deja
<strong>probar con un pedacito del archivo real</strong> antes de guardar nada.
Está en <strong>🎵 Audio</strong> y también en <strong>🎬 Video</strong>: es la misma.
</p>
<ol>
  <li>Barra lateral → <strong>🎵 Audio</strong> o <strong>🎬 Video</strong> → solapa
      <strong>"🎚 Mejorar audio"</strong>.</li>
  <li>Tocá <em>"📁 Elegir audio o video"</em>.</li>
  <li>Elegí un <strong>punto de partida</strong>: <em>Suave</em>, <em>Medio</em>,
      <em>Fuerte</em> o <em>Cámara Gesell</em>. Las perillas se acomodan solas.
      <em>"Todo en cero"</em> las vuelve a dejar sin tocar.</li>
  <li>En <em>"Probar con una parte del archivo"</em>, llevá la barra a un momento donde
      se hable y tocá <em>"▶ Escuchar el original"</em> y después
      <em>"▶ Escuchar con los ajustes"</em>. Son unos 5 segundos: alcanza para comparar.</li>
  <li>Corregí las perillas a oído y volvé a probar las veces que haga falta.</li>
  <li>Cuando te conforme, tocá <em>"🎚 Guardar una copia con el audio mejorado"</em>.
      Si era un video, la imagen queda igual: sólo cambia el sonido.</li>
</ol>
<table>
  <tr><th>Perilla</th><th>Qué hace</th><th>Si te pasás</th></tr>
  <tr><td>Ruido de fondo</td><td>Baja el soplido parejo: aire acondicionado, ventilador, siseo del micrófono.</td><td>La voz suena metálica o «bajo el agua».</td></tr>
  <tr><td>Zumbido y golpes</td><td>Saca los sonidos muy graves: zumbido eléctrico, golpes en la mesa, pasos, motores.</td><td>La voz queda finita.</td></tr>
  <tr><td>Siseo agudo</td><td>Saca los sonidos muy agudos: siseo, chirridos.</td><td>La voz queda apagada y se pierden las eses.</td></tr>
  <tr><td>Realzar la voz</td><td>Levanta las consonantes, que es lo que hace que se entiendan las palabras.</td><td>La voz suena dura y resalta también el ruido.</td></tr>
  <tr><td>Emparejar volumen</td><td>Sube las partes donde se habla bajito y deja como están las fuertes.</td><td>También sube el ruido en los silencios: combinalo con «Ruido de fondo».</td></tr>
  <tr><td>Volumen</td><td>Sube o baja todo por igual.</td><td>Sube el ruido junto con la voz.</td></tr>
</table>
<div class="tip">
  💡 Los puntos de partida son para empezar, no una receta: cada grabación es distinta.
  Lo que manda es lo que escuchás en la prueba.
</div>
<div class="warn">
  ⚠️ El original no se toca: se guarda una copia aparte, con su informe y sus hashes.
  Mejorar el audio <strong>cambia el sonido</strong>; si el material es prueba, se
  presenta el original y la copia mejorada se ofrece como ayuda para escuchar.
</div>

<hr class="section-sep">

<!-- ─── 5c ─── -->
<h2>5c. 🎙 Transcribir: pasar a texto lo que se dice</h2>
<p>
El programa escucha un audio o un video y escribe lo que se dice, separado en tramos
de más o menos una oración, cada uno con su minuto y segundo. Después se puede
<strong>escuchar tramo por tramo y corregir el texto</strong> ahí mismo. Está en
<strong>🎵 Audio</strong> y en <strong>🎬 Video</strong>: es la misma solapa.
</p>
<ol>
  <li>Barra lateral → <strong>🎵 Audio</strong> o <strong>🎬 Video</strong> → solapa
      <strong>"🎙 Transcribir"</strong>.</li>
  <li>Elegí qué transcribir: <em>"📁 Elegir archivos"</em> (uno, o varios a la vez
      con Ctrl o Shift) o <em>"📂 Elegir carpeta"</em> (todos los audios y videos que
      haya en esa carpeta, por ejemplo las notas de voz de un chat). Si alguno no
      tiene audio o no se puede leer, lo deja afuera y te avisa cuál.</li>
  <li>Elegí el <strong>modelo</strong>. Viene elegido el que conviene para esa
      computadora:
    <ul>
      <li><strong>Medio</strong> — el recomendado: muy buena precisión.</li>
      <li><strong>Turbo</strong> — muy buena precisión; conviene en grabaciones largas.</li>
      <li><strong>Chico</strong> — rápido, para una primera pasada o para una computadora con poca memoria.</li>
    </ul>
  </li>
  <li>Si hablan varias personas, marcá <em>"Reconocer quién habla"</em> y decile
      <em>"¿Cuántos hablan?"</em> (viene en 2 personas).</li>
  <li>Tocá <em>"🎙 Transcribir"</em>. La barra muestra el avance y se puede cancelar.
      Mientras trabaja, en el cuadro <strong>"Lo que va transcribiendo"</strong> va
      apareciendo el texto a medida que lo entiende (de a medio minuto de grabación,
      más o menos), con el nombre de cada archivo si son varios.</li>
</ol>
<div class="tip">
  💡 <strong>No hace falta esperar.</strong> El reproductor aparece apenas elegís el
  archivo: podés escuchar la grabación antes de transcribirla y mientras se
  transcribe. Y con varios archivos, cada uno se puede corregir en cuanto sale,
  mientras el programa sigue con los demás.
</div>
<div class="tip">
  💡 Con varios archivos, arriba de la revisión aparece el desplegable
  <strong>"Archivo:"</strong> para pasar de una grabación a otra (mientras se
  transcribe, las que todavía no salieron aparecen apagadas). Si cancelás por la
  mitad, lo que ya salió queda hecho: al tocar otra vez <em>"Transcribir"</em> sigue
  sólo con lo que falta.
</div>

<h3>Revisar y corregir</h3>
<ul>
  <li>A la izquierda queda la lista de <strong>tramos</strong>. El que está sonando se
      marca con 🔊 y en negrita; los que ya revisaste, con ✓.</li>
  <li><em>"▶ Escuchar"</em> reproduce desde el tramo elegido. <em>"◀◀ 10 s"</em> y
      <em>"10 s ▶▶"</em> retroceden y adelantan; <em>"↺ Repetir el tramo"</em> lo vuelve
      a pasar.</li>
  <li><strong>Velocidad:</strong> de 0,5× (más lento, para lo que no se entiende) a 2×
      (para repasar rápido).</li>
  <li>Corregí el texto en el cuadro de abajo. Si te arrepentís,
      <em>"Restaurar el texto original"</em> devuelve lo que había escrito el programa.</li>
  <li>Marcá <em>"Ya revisé este tramo"</em> y seguí con
      <em>"Siguiente sin revisar →"</em>: así sabés siempre por dónde vas.</li>
  <li><em>"✓ Revisado hasta acá"</em> marca de una vez todos los tramos desde el
      principio hasta el que estás mirando. Abajo a la derecha queda escrito
      cuántos llevás y <strong>hasta qué minuto está corregido</strong>.</li>
  <li>Atajos: <em>Ctrl + Espacio</em> escucha o pausa, <em>Ctrl + ← / →</em> retrocede
      o adelanta 10 segundos, <em>Ctrl + Shift + ← / →</em> baja o sube la velocidad
      y <em>Ctrl + R</em> repite el tramo.</li>
</ul>
<div class="tip">
  💡 Lo que vas corrigiendo <strong>se guarda solo</strong>. Si cerrás el programa y
  otro día elegís el mismo archivo, aparece la transcripción por donde la dejaste.
</div>

<h3>👥 Reconocer quién habla</h3>
<p>
El programa distingue las voces y le pone a cada tramo quién lo dice:
<em>Interlocutor 1</em>, <em>Interlocutor 2</em>… El Interlocutor 1 es el primero
que habla. Si en una grabación habla uno solo, no se le pone nada adelante.
</p>
<ul>
  <li>Se puede pedir <strong>antes</strong>, con la casilla, o <strong>después</strong>,
      sobre una transcripción ya hecha, con el botón
      <em>"👥 Reconocer quién habla"</em> (no vuelve a transcribir).</li>
  <li><em>"✏️ Nombres…"</em> cambia «Interlocutor 1» por el nombre o el rol
      (<em>Entrevistadora</em>, <em>Niña</em>). Te muestra una frase de cada uno para
      que sepas quién es quién.</li>
  <li>Si un tramo quedó a nombre de quien no era, corregilo con el desplegable
      <em>"Habla:"</em>. Ahí también está <em>"➕ Otro interlocutor…"</em>.</li>
  <li>Si elegiste una carpeta donde en algunos audios habla una sola persona, en
      <em>"¿Cuántos hablan?"</em> conviene <em>"Que lo descubra solo"</em>: si le
      decís «2 personas», busca dos voces en todos.</li>
</ul>
<div class="warn">
  ⚠️ <strong>Distingue voces, no identifica personas.</strong> Acierta más si le decís
  cuántos hablan; se equivoca más cuando las voces se parecen, cuando hablan a la vez
  o cuando el audio es malo. Controlalo siempre escuchando.
</div>

<h3>Generar el informe</h3>
<ul>
  <li><em>"💾 Generar el informe…"</em> arma un solo documento con la transcripción de
      <strong>todo lo que elegiste</strong> y el <strong>hash SHA-256 de cada
      archivo</strong>: abre con <em>«Transcripción: se analizó el archivo…»</em>.
      Con un solo archivo, el hash va en ese primer párrafo; con varios, cada uno
      lleva su nombre, su tamaño, su duración y su hash antes de lo que se dice.</li>
  <li>Se guarda como documento <strong>.odt</strong> (lo abren LibreOffice y Word),
      <strong>Word</strong> (.docx) o <strong>texto</strong> (.txt). El texto de
      apertura se puede retocar después en el documento.</li>
  <li>Si elegís <strong>subtítulos</strong> (.srt), sale un archivo por cada grabación.</li>
  <li>Con <em>"Con el minuto y segundo de cada tramo"</em> marcado, cada renglón lleva
      su tiempo. Desmarcado, y con los interlocutores reconocidos, sale como un
      <strong>diálogo</strong>: un párrafo por cada intervención
      (<em>Interlocutor 1: … / Interlocutor 2: …</em>).</li>
  <li>Abajo aparece además la constancia técnica de siempre, con los hashes de los
      originales y del documento generado.</li>
  <li><em>"📋 Copiar todo"</em> la deja lista para pegar en otro documento.</li>
</ul>
<div class="tip">
  💡 Funciona <strong>sin internet</strong> y sin placa de video: los modelos viajan en
  la carpeta <code>models</code> del programa. Tarda más o menos lo que dura la
  grabación, y bastante más en una computadora vieja.
</div>
<div class="tip">
  💡 Si la grabación se escucha mal, pasala primero por
  <strong>"🎚 Mejorar audio"</strong> y transcribí la copia mejorada.
</div>
<div class="warn">
  ⚠️ La transcripción automática comete errores, sobre todo con nombres propios, ruido
  o varias personas hablando juntas. Revisala antes de usarla en un documento oficial.
</div>

<hr class="section-sep">

<!-- ─── 6 ─── -->
<h2>6. 🎬 Video</h2>
<table>
  <tr><th>Formato</th><th>Para qué sirve</th></tr>
  <tr><td>MP4</td><td>El más compatible. Funciona en todos los dispositivos.</td></tr>
  <tr><td>MKV</td><td>Video de alta calidad con múltiples pistas de audio/subtítulos.</td></tr>
  <tr><td>AVI</td><td>Formato clásico de Windows. Compatible con programas viejos.</td></tr>
  <tr><td>MOV</td><td>Formato de Apple. Alta calidad.</td></tr>
  <tr><td>WEBM</td><td>Video para internet. Ideal para páginas web.</td></tr>
  <tr><td>GIF</td><td>Convierte video corto en animación. Ideal para clips de 5-10 segundos.</td></tr>
</table>
<h3>💬 Subtítulos automáticos</h3>
<p>
El programa puede escuchar el audio del video y generar subtítulos automáticamente.
</p>
<p><strong>¿Dónde está la opción?</strong> En la pantalla principal de conversión:
cuando agregás uno o más videos, en el panel de opciones aparece
<strong>"💬 Generar subtítulos automáticos"</strong>. (Si no agregaste ningún video, la opción no se muestra.)</p>
<ol>
  <li><strong>Activar o desactivar:</strong> marcá o desmarcá la casilla. Desmarcada = no se generan subtítulos.</li>
  <li><strong>Idioma del audio:</strong> elegí el idioma que se habla en el video, o dejá "Detectar automáticamente".</li>
  <li><strong>"Incluir subtítulos dentro del video":</strong> si la marcás, los subtítulos quedan grabados en la imagen del video.
      Si no, se genera un archivo <strong>.srt</strong> junto al video convertido (podés activarlos o desactivarlos en el reproductor).</li>
</ol>
<p>
Funciona sin internet: lo que necesita para reconocer la voz viene en la carpeta del programa.
</p>
<div class="warn">
  ⚠️ Los subtítulos automáticos pueden cometer errores. Revisalos antes de usar en documentos oficiales.
</div>
<div class="tip">
  💡 Si lo que necesitás es <strong>el texto para revisarlo y corregirlo</strong>, o saber
  quién dice cada cosa, usá la solapa <strong>"🎙 Transcribir"</strong> del módulo Video
  (punto 5c): también guarda subtítulos .srt, ya corregidos.
</div>

<hr class="section-sep">

<!-- ─── 7 ─── -->
<h2>7. ✂️ Partir un video en partes</h2>
<p>
Sirve cuando tenés un video muy grande para mandar por correo (~25 MB),
por WhatsApp (~16 MB) o para subir a un sistema con límite de tamaño.
</p>

<h3>Cómo hacerlo</h3>
<ol>
  <li>Barra lateral → <strong>🎬 Video</strong> → solapa <strong>"✂️ Partir Video"</strong>.</li>
  <li>Tocá <em>"📁 Elegir video"</em> y buscá el archivo.</li>
  <li>Poné el <strong>tamaño máximo de cada parte</strong> en MB.</li>
  <li>Si querés, cambiá la carpeta de salida con <em>"Cambiar"</em>.</li>
  <li>Tocá <em>"✂️ Partir video"</em>. Al terminar,
      <em>"📂 Abrir carpeta de resultados"</em> te muestra las partes.</li>
</ol>
<div class="tip">
  💡 El partidor <strong>no re-codifica</strong> el video: no pierde calidad y tarda poco,
  porque solo corta en los puntos indicados.
</div>
<div class="tip">
  💡 Con un video largo, la barra muestra el <strong>porcentaje real</strong> desde que
  arranca. La huella (hash) del original se calcula al mismo tiempo que se corta, así
  no hay que esperar a que termine de leerlo entero para empezar.
</div>
<div class="tip">
  💡 Si el video tiene que entrar en un límite de tamaño (un correo, un portal),
  usá la otra solapa, <strong>"📦 Ajustar tamaño"</strong>: lo comprime o lo corta y
  genera un informe con los hashes.
</div>

<hr class="section-sep">

<!-- ─── 7d ─── -->
<h2>7d. 🗺️ Mapa del video: toda la grabación en una imagen</h2>
<p>
Tenés tres horas de cámara de seguridad y no sabés en qué momento pasó lo que
buscás. Mirarlas enteras no es opción y arrastrar la barra a ciegas tampoco.
El <strong>mapa</strong> arma <strong>una sola imagen</strong> con miniaturas de toda la
grabación, cada una con su minuto y segundo: se ve la película completa de un
vistazo y se ubica el tramo en segundos.
</p>
<ol>
  <li>Barra lateral → <strong>🎬 Video</strong> → solapa <strong>"🗺️ Mapa del video"</strong>.</li>
  <li>Elegí el video. El programa calcula solo cada cuánto conviene sacar una
      miniatura (un intervalo redondo: 30 s, 1 minuto, 5 minutos…) y te avisa cuántas
      van a salir. Si querés más detalle, destildá <em>Automático</em> y poné el
      intervalo a mano.</li>
  <li>Tocá <strong>"🗺️ Armar el mapa"</strong>. Queda guardado como
      <code>«nombre»_mapa.png</code> en la carpeta de salida.</li>
  <li><strong>Tocá cualquier miniatura</strong>: el programa te dice de qué momento es
      y te ofrece el botón <em>"📸 Abrir este momento en «Capturar fotograma»"</em>.
      Al tocarlo saltás a la otra solapa, con el video abierto y parado justo ahí,
      listo para moverte de a un fotograma y capturar.</li>
</ol>
<div class="tip">
  💡 Ese es el circuito completo: <strong>el mapa para encontrar, la captura para
  llevarse la prueba.</strong> Las miniaturas del mapa están reducidas (sirven para
  ubicarse, no para observar detalles); el fotograma se guarda en la resolución
  original desde la otra solapa.
</div>
<div class="tip">
  💡 En un video largo, el intervalo automático reparte unas 60 miniaturas. Si ponés
  un intervalo muy chico salen cientos, el mapa tarda mucho y queda una imagen enorme:
  el programa te lo avisa antes de empezar.
</div>

<hr class="section-sep">

<!-- ─── 7e ─── -->
<h2>7e. 📸 Capturar el fotograma exacto de un video</h2>
<p>
Mirás la grabación de una cámara de seguridad y en un momento aparece lo que
importa: el choque, la persona, la patente. Esta herramienta te deja quedarte con
<strong>esa imagen</strong>, con el <strong>minuto y segundo precisos</strong> y con una
constancia que permite verificar después de dónde salió.
</p>
<ol>
  <li>Barra lateral → <strong>🎬 Video</strong> → solapa <strong>"📸 Capturar fotograma"</strong>.</li>
  <li>Tocá <em>"📁 Elegir video"</em>. Arriba aparece la ficha: duración, medidas,
      códec, cuadros por segundo y, si el archivo la trae, la hora en que empezó la grabación.</li>
  <li>Buscá el momento. Podés arrastrar la barra, escribir el tiempo
      (<code>00:04:17.320</code>) y tocar <em>Ir</em>, o moverte con los botones:
      <strong>±10 s</strong>, <strong>±1 s</strong> y <strong>±1 fotograma</strong>.
      Con el teclado es más cómodo: <strong>← y →</strong> mueven de a un fotograma,
      <strong>Shift+← / →</strong> de a un segundo, <strong>Re Pág / Av Pág</strong> de a diez.</li>
  <li>Debajo de la imagen, el cartel azul te dice siempre en qué fotograma estás:
      tiempo exacto, número de fotograma y hora estimada del hecho.</li>
  <li>Tocá <strong>"📸 Capturar este fotograma"</strong>. Se guardan dos archivos:
      la imagen en PNG (con el tiempo en el nombre) y la constancia en TXT.</li>
</ol>
<h3>Los dos botones de abajo</h3>
<table>
  <tr><th>Botón</th><th>Para qué sirve</th></tr>
  <tr><td>🎞️ Ráfaga</td><td>Guarda <strong>todos</strong> los fotogramas alrededor del momento
      elegido (por ejemplo 2 segundos antes y después). El hecho no siempre cae en el
      fotograma que uno eligió primero: con la ráfaga te llevás la secuencia completa.</td></tr>
  <tr><td>✂️ Guardar el video original</td><td>Recorta un pedazo del video
      <strong>sin recodificar</strong>: los bits son los del archivo original. Sirve para
      adjuntar junto a la foto.</td></tr>
</table>
<div class="tip">
  💡 <strong>El tiempo que se guarda es el del fotograma, no el que pediste.</strong>
  Si pedís el segundo 17.320 y el fotograma más cercano está en 17.280, tanto el
  cartel como la constancia dicen 17.280. Nunca se estampa un dato aproximado.
</div>
<div class="tip">
  💡 La imagen sale en <strong>PNG</strong>, en la resolución original, sin recortes,
  sin escalado y sin ajustes de color. No se usa JPG a propósito: el JPG inventa
  manchas en los bordes y eso arruina una ampliación posterior.
</div>
<div class="warn">
  ⚠️ <strong>Sobre la hora del hecho.</strong> La hora real se calcula sumando el tiempo
  transcurrido a la hora de inicio que declara el archivo. Muchos equipos no la
  graban, o la graban con la hora del aparato mal puesta, y en esos casos el programa
  te avisa que no la puede determinar en vez de inventarla. <strong>Si la cámara imprime
  la hora sobre la imagen, esa es la que vale</strong>, y queda dentro de la captura.
</div>
<div class="warn">
  ⚠️ Si el video es de <strong>cadencia variable</strong> (la cámara graba más cuadros
  cuando hay movimiento), no se puede numerar los fotogramas y el programa lo dice:
  se informa el tiempo exacto de cada uno, que es el dato firme.
</div>
<div class="tip">
  💡 La constancia lleva el <strong>SHA-256 y el MD5</strong> del video y de la imagen. Con
  esos números, cualquiera puede comprobar después que la foto salió de ese video y
  que nadie la retocó. Para verificarlos, usá <strong>🔢 Extraer hash</strong>.
</div>

<hr class="section-sep">

<!-- ─── 7c ─── -->
<h2>7c. ✍️ Escribir un texto sin salir del programa</h2>
<p>
Para pasar un texto a PDF antes había que escribirlo en otro programa,
guardarlo, traerlo a la cola y recién ahí convertirlo. Con
<strong>✍️ Escribir</strong> se escribe acá y listo.
</p>
<ol>
  <li>Barra lateral → <strong>✍️ Escribir</strong>.</li>
  <li>Escribí <strong>como escribís siempre</strong>, igual que en un Word. No
      hace falta aprender nada raro. A la derecha se ve la
      <strong>vista previa</strong> de cómo va a quedar; si no la querés,
      destildá <em>"👁 Vista previa"</em>.</li>
  <li>Si sólo querías el texto para pegarlo en otro lado —un prompt, por
      ejemplo— tocá <em>"📋 Copiar todo"</em> y no hace falta guardar nada.</li>
  <li>Si lo querés como archivo, elegí el formato en <em>"Guardar como:"</em>
      y tocá <em>"💾 Guardar como..."</em>.</li>
</ol>

<h3>Cómo escribir para que salga bien formateado</h3>
<p>
El programa mira <strong>cómo escribiste</strong> y arma los títulos y las
listas solo. Son las mismas costumbres de siempre al redactar un escrito:
</p>
<table>
  <tr><th>Si escribís...</th><th>Queda como</th><th>Ejemplo</th></tr>
  <tr><td>Un renglón corto <strong>TODO EN MAYÚSCULAS</strong></td>
      <td>Título</td><td><code>SOLICITA ALLANAMIENTO</code></td></tr>
  <tr><td>Un renglón que empieza con <strong>número romano</strong></td>
      <td>Título de sección</td><td><code>I.- OBJETO:</code></td></tr>
  <tr><td>Un renglón que empieza con <strong>letra y paréntesis</strong></td>
      <td>Inciso destacado</td><td><code>a) El registro del inmueble.</code></td></tr>
  <tr><td>Un renglón que empieza con <strong>guión</strong></td>
      <td>Viñeta de una lista</td><td><code>- teléfonos celulares</code></td></tr>
  <tr><td>Un renglón que empieza con <strong>número y punto</strong></td>
      <td>Lista numerada</td><td><code>1. Se remite copia.</code></td></tr>
  <tr><td>Un <strong>renglón en blanco</strong></td>
      <td>Separa un párrafo del siguiente</td><td></td></tr>
</table>
<div class="tip">
  💡 <strong>El punto importa.</strong> Si un renglón no termina con punto y el
  que sigue empieza con minúscula, el programa entiende que es la misma oración
  cortada al medio y los une. Si terminás con punto, arranca renglón nuevo. Por
  eso conviene puntuar como se puntúa siempre.
</div>
<div class="tip">
  💡 <strong>¿Querés el Markdown para copiar y pegar, sin guardar nada?</strong>
  Arriba de la vista previa, cambiá <em>"Vista:"</em> a <strong>Markdown</strong>:
  ahí se ve el código que armó el programa, con los <code>#</code> de los
  títulos y los guiones de las listas. Con el botón
  <em>"📋 Copiar en Markdown"</em> te lo llevás al portapapeles y listo, no
  hace falta crear ningún archivo. Es lo típico para un prompt.
</div>
<div class="tip">
  💡 Si ya sabés <strong>Markdown</strong> y preferís escribirlo vos, cambiá
  <em>"Escribo en:"</em> a <strong>Markdown</strong> y el texto se guarda tal
  como lo escribiste, sin que el programa interprete nada.
</div>
<div class="tip">
  💡 El <strong>.txt siempre sale tal cual lo escribiste</strong>, sin ningún
  agregado: es texto plano. Los otros formatos (PDF, Word, ODT…) son los que
  salen con los títulos y las listas ya armados.
</div>
<div class="tip">
  💡 <strong>El borrador se guarda solo.</strong> Si cerrás el programa (o se
  corta la luz), al volver a entrar el texto sigue ahí. Se borra recién cuando
  tocás <em>"🗑 Limpiar"</em>.
</div>
<div class="tip">
  💡 Abajo a la izquierda te dice cuántos caracteres, palabras y
  <strong>tokens aproximados</strong> lleva el texto. Sirve cuando estás
  armando un prompt para una inteligencia artificial y hay un límite.
</div>

<hr class="section-sep">

<!-- ─── 7b ─── -->
<h2>7b. 📄 El módulo PDF</h2>
<p>
Todo lo que tenga que ver con PDF está en un solo lugar: el módulo
<strong>📄 PDF</strong> de la barra lateral izquierda. Adentro hay
<strong>nueve solapas</strong>, y cada una dice con un verbo lo que hace:
</p>
<table>
  <tr><th>Solapa</th><th>Para qué es</th></tr>
  <tr><td>🔗 Unir archivos</td><td>Juntar varios PDF en uno solo. Opcionalmente, partir el resultado.</td></tr>
  <tr><td>✂️ Partir</td><td>Cortar un PDF que ya tenés: por tamaño, por cantidad de páginas o quedándote con un tramo.</td></tr>
  <tr><td>📖 Hojas dobles</td><td>Separar las hojas escaneadas de a dos páginas (oficio apaisada) en hojas A4 sueltas, y reconocer su texto.</td></tr>
  <tr><td>📦 Ajustar tamaño</td><td>Dejar una carpeta entera de PDF lista para subir a un portal con límite: parte los que pasan de 10 MB y arma las tandas de 5.</td></tr>
  <tr><td>📑 Organizar páginas</td><td>Reordenar, rotar y eliminar páginas.</td></tr>
  <tr><td>🖋 Firmar</td><td>Firma digital con token USB o certificado en archivo.</td></tr>
  <tr><td>🔍 Reconocer texto</td><td>OCR: hacer que un escaneo se pueda buscar y copiar.</td></tr>
  <tr><td>📊 Pasar a Excel</td><td>Llevar a una planilla la tabla de un PDF (un resumen bancario, un listado), aunque sea un escaneo. Tiene su propia sección: <strong>7f</strong>.</td></tr>
  <tr><td>🛠 Herramientas</td><td>Comprimir, proteger con contraseña, quitar contraseña, reparar.</td></tr>
</table>
<div class="tip">
  💡 Todo se hace en tu computadora. Ningún archivo se sube a internet, y el
  original nunca se modifica: siempre se genera una copia nueva.
</div>

<h3>🔗 Cómo unir varios PDF en uno</h3>
<ol>
  <li>Barra lateral → <strong>📄 PDF</strong> → solapa <strong>"🔗 Unir archivos"</strong>.</li>
  <li>Tocá <em>"➕ Agregar PDFs..."</em> para elegir archivos sueltos, o
      <em>"📁 Agregar carpeta..."</em> para sumar todos los PDF de una carpeta de una vez.
      Podés repetir para ir juntando de varios lugares.</li>
  <li><strong>Acomodá el orden</strong>: el número de cada fila es el orden en que se van a unir.
      Arrastrá con el mouse, usá <em>"↑ Subir"</em> y <em>"↓ Bajar"</em>,
      o llevalo directo a un número con <em>"Mover"</em>.</li>
  <li>Abajo, en <em>"¿Partir el resultado en varios archivos?"</em>, dejá
      <strong>"No"</strong> si querés un único documento, o marcá <strong>"Sí"</strong>
      y poné el tamaño máximo por parte.</li>
  <li>Tocá <em>"🔗 Unir y guardar..."</em> y elegí dónde guardarlo.</li>
</ol>
<div class="tip">
  💡 Si lo tenés que subir a un portal con límite, marcá "Sí" y tocá el botón
  <em>"10 MB"</em>: es el límite más habitual.
</div>

<h3>✂️ Cómo partir un PDF</h3>
<ol>
  <li>Barra lateral → <strong>📄 PDF</strong> → solapa <strong>"✂️ Partir"</strong>.</li>
  <li>Tocá <em>"📄 Elegir PDF..."</em>. Te muestra cuántas páginas tiene y cuánto pesa.</li>
  <li>Elegí <strong>cómo</strong> partirlo:
    <ul>
      <li><strong>Por tamaño</strong> — "en partes que no superen X MB". Para mandar por
          mail o subir a un sistema con límite.</li>
      <li><strong>Por cantidad de páginas</strong> — "en partes de X páginas cada una".
          Para separar un documento largo en partes.</li>
      <li><strong>Quedarme con un tramo</strong> — extrae de la página X a la Y y descarta
          el resto.</li>
    </ul>
  </li>
  <li>Tocá <em>"✂️ Partir el PDF"</em> y elegí la carpeta donde dejar las partes
      (si extraés un tramo, te pide el nombre del archivo).</li>
</ol>

<h3>📖 Cómo separar hojas dobles en A4</h3>
<p>
Para documentos escaneados de a dos páginas por hoja: una hoja oficio apaisada
con la página 1 a la izquierda y la 2 a la derecha.
</p>
<ol>
  <li>Barra lateral → <strong>📄 PDF</strong> → solapa <strong>"📖 Hojas dobles"</strong>.</li>
  <li>Sumá lo que quieras procesar con <em>"➕ Agregar archivos..."</em> (uno o varios)
      o <em>"📁 Agregar carpeta..."</em> (todos los PDF y fotos de esa carpeta). Podés mezclar
      PDF y fotos (JPG, PNG...) sin pasarlas antes a PDF: cada foto es una hoja. Quedan
      ordenados por nombre (IMG_0001, IMG_0002...) y podés arrastrarlos para cambiar el orden.
      Abajo te dice cuántas hojas son dobles y cuántas páginas A4 van a quedar.</li>
  <li>Elegí si querés <strong>todo junto en un solo resultado</strong> o
      <strong>uno por cada archivo</strong> (en ese caso te pide la carpeta).</li>
  <li>Elegí qué página va primero (lo normal es la de la izquierda).</li>
  <li>Elegí qué querés obtener: sólo el PDF en A4, el PDF en A4 con el texto buscable,
      o un archivo de texto con lo que dice cada página.</li>
  <li>Tocá <em>"📖 Separar las hojas"</em> y elegí dónde guardarlo. Al terminar te muestra
      dónde quedó, y <em>"📂 Abrir carpeta de resultados"</em> te lleva directo.</li>
</ol>
<div class="tip">
El corte se hace en el pliegue que se ve en el escaneo, aunque no esté justo en la mitad.
Las hojas que ya son simples pasan a A4 sin cortarse. Si en <strong>"🔍 Reconocer texto"</strong>
elegís un PDF con hojas apaisadas, también las separa antes de leerlas: leídas juntas,
el OCR mezcla los renglones de las dos páginas.
</div>

<h3>📦 Preparar una carpeta de PDF con límite de tamaño</h3>
<p>
Cuando tenés 30 PDF para subir a un portal que acepta pocos archivos por vez y
con un tamaño máximo, hacerlo a mano es tedioso: hay que ir de a 5, controlando
que ninguno pase de 10 MB, y es fácil copiar uno de más o saltearse otro. Esta
solapa lo hace sola.
</p>
<ol>
  <li>Barra lateral → <strong>📄 PDF</strong> → solapa
      <strong>"📦 Ajustar tamaño"</strong>.</li>
  <li>Tocá <em>"📁 Elegir carpeta..."</em> y elegí la carpeta con los PDF
      (o <em>"📄 Elegir archivos..."</em> si querés algunos sueltos). Te avisa
      cuántos hay y cuántos pasan del límite.</li>
  <li>El <strong>máximo por archivo</strong> viene en 10 MB y las
      <strong>tandas</strong> en 5, que son los límites más habituales.
      Podés cambiar los dos.</li>
  <li>Si querés, cambiá la <strong>carpeta de destino</strong>.</li>
  <li>Tocá <em>"📦 Preparar la carpeta"</em>.</li>
</ol>
<p>
Queda una carpeta con <strong>Tanda_1</strong>, <strong>Tanda_2</strong>… de 5
archivos cada una, más el informe técnico con los hashes. Los PDF que ya
entraban en el límite se copian tal cual; los que se pasaban quedan partidos
como <em>documento_Parte_1.pdf</em>, <em>documento_Parte_2.pdf</em>…
</p>
<div class="tip">
  💡 Los originales no se tocan: se trabaja siempre sobre copias.
</div>
<div class="warn">
  ⚠️ Si una sola página pesa más que el límite, esa parte queda más grande y el
  programa te lo avisa al terminar. En ese caso, comprimí primero el PDF desde
  la solapa <strong>"🛠 Herramientas"</strong>.
</div>

<h3>📑 Organizar páginas</h3>
<ol>
  <li>Tocá <em>"📂 Elegir PDF..."</em> — se muestran las <strong>miniaturas</strong> de todas las páginas.</li>
  <li><strong>Cambiar el orden:</strong> arrastrá las miniaturas con el mouse a la posición que quieras.</li>
  <li><strong>Eliminar páginas:</strong> seleccioná una o varias (Ctrl+clic) y tocá <em>"🗑 Eliminar seleccionadas"</em> o la tecla <em>Supr</em>.</li>
  <li><strong>Rotar páginas:</strong> con las páginas seleccionadas, usá <em>"↺ Rotar izquierda"</em> o <em>"↻ Rotar derecha"</em>.</li>
  <li><strong>Una hoja bien y la siguiente de cabeza:</strong> pasa al escanear un libro
      o un documento dándolo vuelta. No hace falta ir una por una:
      <em>"🙃 Voltear una por medio"</em> gira 180° de una sola vez todas las hojas
      pares (2, 4, 6…) o todas las impares (1, 3, 5…), según cuáles hayan quedado al revés.</li>
  <li>Tocá <em>"💾 Guardar como..."</em> para generar el PDF nuevo.</li>
</ol>
<div class="tip">
  💡 El archivo original nunca se modifica: siempre se guarda una copia nueva. Si te equivocaste, <em>"↩ Deshacer todo"</em> recarga las páginas como estaban.
</div>

<h3>🛠 Herramientas</h3>
<table>
  <tr><th>Herramienta</th><th>Qué hace</th></tr>
  <tr><td>🗜 Comprimir</td><td>Reduce el peso del PDF recomprimiendo sus imágenes. Tres niveles: suave, media y fuerte. El texto nunca pierde calidad.</td></tr>
  <tr><td>🔒 Proteger</td><td>Le pone contraseña al PDF (cifrado AES). Sin la contraseña no se puede abrir.</td></tr>
  <tr><td>🔓 Quitar contraseña</td><td>Genera una copia sin contraseña de un PDF protegido. <strong>Hay que conocer la contraseña actual</strong>: no sirve para vulnerar documentos ajenos.</td></tr>
  <tr><td>🖋 Firmar</td><td>Firma digital estándar (PAdES) con sello visible opcional. Funciona con un certificado en archivo (.pfx/.p12) o con un <strong>token USB</strong> de firma digital.</td></tr>
  <tr><td>🩹 Reparar</td><td>Intenta recuperar un PDF dañado que no abre o muestra errores, reescribiendo su estructura interna.</td></tr>
</table>
<div class="warn">
  ⚠️ Si protegés un PDF, anotá la contraseña en un lugar seguro. No hay forma de recuperarla.
</div>

<h3>🖋 Firmar con token USB</h3>

<p>El <strong>token</strong> es esa especie de pendrive que te entregaron junto con tu
certificado de firma digital. Adentro guarda tu certificado de manera que nadie lo pueda
copiar: para usarlo hay que tenerlo enchufado y saber el <strong>PIN</strong>.</p>

<h4>Paso a paso (lo normal)</h4>
<ol>
  <li><strong>Enchufá el token</strong> en cualquier puerto USB de la computadora.</li>
  <li>Andá a <em>🧰 Editar PDF → 🖋 Firmar</em> (es una solapa propia, al lado de
      Herramientas) y elegí la opción <strong>"Token USB (PKCS#11)"</strong>.</li>
  <li>El programa busca el token solo y te muestra un cartel:
    <ul>
      <li><strong>Verde ✅ "Token detectado"</strong> → todo listo, seguí al paso 4.</li>
      <li><strong>Naranja ⚠ "Falta el programa del token"</strong> → leé más abajo
          <em>"Si te aparece «Falta el programa del token»"</em>.</li>
      <li><strong>Naranja ⚠ "No encuentro el token"</strong> → el token no está enchufado
          o no hace buen contacto: sacalo, volvé a ponerlo y tocá
          <em>"🔄 Buscar el token de nuevo"</em>.</li>
    </ul>
  </li>
  <li>Escribí el <strong>PIN</strong> de tu token.</li>
  <li>Opcional pero recomendado la primera vez: tocá <strong>"🔍 Probar token"</strong>.
      No firma nada; sólo se conecta y te muestra qué certificado hay adentro, a nombre
      de quién está y hasta cuándo vale. Sirve para confirmar que el PIN es correcto
      <em>antes</em> de firmar.</li>
  <li>Arriba de todo, tocá <em>"📄 Elegir PDF..."</em> y elegí el documento.</li>
  <li>Elegí <strong>en qué hoja</strong> se va a ver el sello (la primera, la última
      o una en particular) y <strong>en qué lugar</strong> de la hoja, con la grilla
      de 9 posiciones. La <strong>vista previa</strong> de la izquierda te muestra
      el recuadro exactamente donde va a quedar.</li>
  <li>Si querés que el sello diga tu cargo, escribilo en
      <strong>"Leyenda debajo de tu nombre"</strong> (ver abajo). Se hace una sola vez.</li>
  <li>Tocá <em>"🖋 Firmar el PDF"</em> y elegí dónde guardar la copia firmada. Listo.</li>
</ol>

<h4>Qué dice el sello y cómo ponerle tu cargo</h4>
<p>El sello tiene tres partes:</p>
<table>
  <tr><th>Parte</th><th>De dónde sale</th></tr>
  <tr><td>Tu nombre</td><td>Del certificado que está dentro del token. No se escribe ni se puede cambiar acá: es el que cargó la autoridad que te lo emitió.</td></tr>
  <tr><td>La leyenda</td><td>La escribís vos, en el cuadro <strong>"Leyenda debajo de tu nombre"</strong> de la solapa Firmar. Es opcional.</td></tr>
  <tr><td>La fecha y la hora</td><td>Las pone el programa en el momento de firmar.</td></tr>
</table>
<p>En la leyenda va lo que quieras que acompañe a tu nombre: el cargo, la dependencia,
la ciudad. <strong>Cada renglón que escribas es un renglón del sello</strong>. Por ejemplo:</p>
<p><code>Jefe de Departamento</code><br>
<code>Área de Administración</code><br>
<code>Ciudad</code></p>
<p>Justo debajo, el recuadro <em>"Así va a decir el sello"</em> te muestra el texto completo
tal como va a quedar. La leyenda <strong>se guarda sola</strong>: la próxima vez que abras
el programa ya está puesta, y sólo la tocás si cambiás de cargo o de dependencia. Si
dejás el cuadro vacío, el sello lleva sólo el nombre y la fecha.</p>
<div class="tip">
  💡 Hasta 6 renglones. Un renglón muy largo se parte solo en dos, y el recuadro del
  sello crece para que la letra no se achique: mirá la vista previa para ver cuánto
  lugar ocupa en la hoja.
</div>

<div class="tip">
  💡 El sello se ve en <strong>una sola hoja</strong>, pero la firma protege
  <strong>todo el documento</strong>: si alguien cambia cualquier página, la firma
  queda inválida. Es exactamente como trabajan los firmadores oficiales. Por eso no
  existe la opción de "firmar todas las páginas": no haría el documento más seguro,
  sólo llenaría el archivo de sellos repetidos.
</div>
<div class="tip">
  💡 Si desmarcás <em>"Mostrar el sello en el PDF"</em>, la firma sigue siendo
  igual de válida pero no se ve ningún recuadro en el documento.
</div>

<h4>Si te aparece «Falta el programa del token»</h4>
<p>Windows reconoce que enchufaste algo, pero todavía no sabe cómo hablar con tu token.
Falta instalar el <strong>programa del fabricante</strong> (se lo llama
<em>driver</em> o <em>middleware</em>). Es gratis y se instala una sola vez.</p>
<p>El cartel naranja te dice <strong>la marca de tu token y el nombre exacto del programa
que necesitás</strong>, y al lado te aparece el botón
<strong>"⬇ Cómo instalarlo"</strong>. Tocalo: te muestra el paso a paso para tu marca
y te abre directamente la página de descarga en el navegador. No hace falta que
busques nada a mano.</p>

<p>Estas son las marcas que el programa reconoce solo:</p>
<table>
  <tr><th>Marca del token</th><th>Programa a instalar</th><th>Dónde lo busca la app</th></tr>
  <tr><td>SafeNet / Aladdin eToken</td><td>SafeNet Authentication Client</td><td>Sitio de DigiCert / Thales</td></tr>
  <tr><td>Gemalto / Thales IDPrime</td><td>SafeNet Authentication Client</td><td>Sitio de DigiCert / Thales</td></tr>
  <tr><td>ePass 2003 (Feitian)</td><td>ePass2003 (middleware de Feitian)</td><td>Página de soporte de Feitian</td></tr>
  <tr><td>YubiKey</td><td>YubiKey Smart Card Minidriver</td><td>Sitio de Yubico: descarga abierta</td></tr>
  <tr><td>TokenMe (Macroseguridad)</td><td>Macroseguridad TokenMe</td><td>Sitio de Macroseguridad (Argentina)</td></tr>
  <tr><td>Bit4id</td><td>Bit4id middleware</td><td>Búsqueda del sitio oficial</td></tr>
  <tr><td>Athena IDProtect</td><td>IDProtect Client</td><td>Búsqueda del sitio oficial</td></tr>
  <tr><td>Watchdata WatchKey</td><td>WatchKey middleware</td><td>Búsqueda del sitio oficial</td></tr>
  <tr><td>mToken CryptoID / CryptoFIPS (Longmai)</td><td>mToken middleware</td><td>Búsqueda del sitio oficial</td></tr>
  <tr><td>CardOS / Atos</td><td>CardOS API</td><td>Búsqueda del sitio oficial</td></tr>
  <tr><td>Otras marcas</td><td>OpenSC (comodín gratuito)</td><td>Página oficial de OpenSC</td></tr>
</table>

<div class="tip">
  💡 Si el token te lo dio un organismo (una dependencia pública, un colegio
  profesional o una autoridad certificante), lo más rápido de todo es pedirles a ellos
  el instalador o el instructivo: es el mismo programa, pero te aseguran la versión
  exacta que ellos usan.
</div>

<h4>Si cambiaste de token y te aparece «El programa instalado es de otro token»</h4>
<p>Cada marca de token trae su propio programa, y el de una marca <strong>no sabe leer
el token de otra</strong>. Si antes usabas un token y ahora te dieron uno nuevo de otra
marca, Windows te muestra el token enchufado y la app encuentra un programa instalado
(el del token viejo), pero no aparece ningún certificado.</p>
<p>La solución es instalar el programa que corresponde al token nuevo: el cartel te dice
cuál es y el botón <strong>"⬇ Cómo instalarlo"</strong> te lleva a la descarga
(o lo instala directamente, si es uno de los que vienen con el programa).
<strong>Al programa viejo no hace falta desinstalarlo</strong>, no molesta: pueden
convivir los dos y la app usa el que corresponda en cada caso.</p>

<h4>Qué hacer con lo que descargaste</h4>
<ol>
  <li><strong>Si bajaste un archivo .zip</strong>: hacé clic derecho sobre él →
      <em>"Extraer todo..."</em> → <em>"Extraer"</em>. Se abre una carpeta con el
      instalador adentro.</li>
  <li>Buscá el archivo que termina en <strong>.exe</strong> o <strong>.msi</strong>
      (suele llamarse <em>setup</em>, <em>install</em> o como el programa).</li>
  <li>Hacé <strong>clic derecho sobre él → "Ejecutar como administrador"</strong>.
      Si Windows pregunta <em>"¿Querés permitir que esta aplicación haga cambios?"</em>,
      respondé <strong>Sí</strong>.</li>
  <li>Seguí el instalador tocando <em>Siguiente</em> hasta el final y aceptando los
      términos. No hace falta cambiar ninguna opción: dejá todo como viene.</li>
  <li>Cuando termine, <strong>reiniciá la computadora</strong> si te lo pide.</li>
  <li>Volvé a abrir esta aplicación, enchufá el token y tocá
      <em>"🔄 Buscar el token de nuevo"</em>. El cartel tiene que ponerse
      <strong>verde ✅</strong>.</li>
</ol>
<div class="warn">
  ⚠️ Descargá el programa <strong>sólo del sitio oficial del fabricante</strong> o del
  organismo que te entregó el certificado. Nunca de un sitio cualquiera: es el programa
  que maneja tu firma.
</div>

<h4>Si sabés lo que hacés</h4>
<p>Dentro de <em>"Opciones avanzadas"</em> podés elegir a mano el archivo del driver
(la <em>DLL PKCS#11</em>) si tenés varios instalados o si tu token es de una marca
poco común, y también indicar la etiqueta del certificado cuando el token guarda
más de uno. Si lo dejás vacío, el programa elige solo.</p>

<div class="warn">
  ⚠️ Cuidado con el PIN: si lo escribís mal varias veces seguidas, el token se
  <strong>bloquea</strong> y hay que desbloquearlo con el código PUK o volver al
  organismo que lo emitió. Ante la duda, usá primero <em>"🔍 Probar token"</em>.
</div>
<div class="tip">
  💡 La firma cumple el estándar PAdES: se verifica en Adobe Acrobat y en los validadores
  oficiales. El sello visible muestra el nombre del firmante y la fecha. El PDF original
  nunca se modifica: se guarda una copia firmada aparte. Si no tenés token, podés firmar
  igual con un certificado en archivo .pfx/.p12 y su contraseña.
</div>

<hr class="section-sep">

<!-- ─── 7f ─── -->
<h2>7f. 📊 Pasar a Excel la tabla de un PDF</h2>
<p>
Un resumen bancario, un listado de llamadas, una planilla que te mandaron en PDF:
se ve como una tabla, pero no se puede ordenar, filtrar ni sumar. La solapa
<strong>"📊 Pasar a Excel"</strong> del módulo <strong>📄 PDF</strong> la convierte en
una planilla de verdad (<code>.xlsx</code> o <code>.csv</code>). Vos marcás sobre la hoja
dónde termina cada columna y el programa te va mostrando abajo cómo queda, antes de guardar.
</p>
<p>
Sirve tanto para un PDF con texto como para un <strong>escaneo</strong> (una foto de la
hoja): en ese caso lee la imagen con OCR respetando el lugar de cada palabra, para que las
columnas no se mezclen.
</p>

<h3>Cómo se ve la solapa</h3>
<table>
  <tr><th>Dónde</th><th>Qué hay</th></tr>
  <tr><td>A la izquierda</td><td>Las tarjetas para configurar: cargar el archivo, las miniaturas de las páginas, los grupos, el formato del Excel, el OCR, los cortes de columna, la receta y la rotación. Abajo de todo, fijo, el botón <em>"⚡ PREPARAR → EXCEL / CSV"</em>.</td></tr>
  <tr><td>A la derecha, arriba</td><td>El <strong>visor</strong>: la página del PDF, donde marcás las columnas (líneas rojas), el inicio de la tabla (línea azul) y el final (línea verde).</td></tr>
  <tr><td>A la derecha, abajo</td><td>La <strong>previsualización</strong>: la tabla tal como va a quedar en el Excel.</td></tr>
</table>

<h3>Paso a paso: convertir un PDF</h3>
<ol>
  <li>Barra lateral → <strong>📄 PDF</strong> → solapa <strong>"📊 Pasar a Excel"</strong>.</li>
  <li>Tocá <em>"📂 Cargar Fuente de Datos"</em> y elegí el PDF. A la izquierda aparecen las
      miniaturas. Hacé <strong>doble clic</strong> en una para verla en el visor.</li>
  <li>Mirá la hoja: ¿cuántas columnas tiene? ¿Hay un título arriba que no querés?</li>
  <li>En la tarjeta <em>"Configuración de grupos"</em>, solapa <strong>G1</strong>, poné de qué
      página a qué página está la tabla (<em>"Págs:"</em>).</li>
  <li>Tocá <em>"🔄 Auto"</em>: el programa mira los espacios en blanco y propone las columnas.
      Aparecen como líneas rojas en el visor.</li>
  <li>Si alguna quedó mal, <strong>arrastrá la línea roja</strong>. Un clic izquierdo en el visor
      agrega una columna; un clic derecho sobre una línea la borra. La previsualización se
      actualiza sola a los pocos segundos. Si te equivocaste, <em>"↩ Volver"</em> deshace.</li>
  <li>Si arriba hay un encabezado que no querés (nombre del cliente, número de cuenta), tocá
      <em>"+ Inicio tabla"</em> y arrastrá la línea azul hasta el renglón de títulos de la tabla.
      Lo mismo con <em>"+ Fin tabla"</em> (línea verde) si molesta el pie de página.</li>
  <li>Tocá <em>"⚡ PREPARAR → EXCEL / CSV"</em>. Te pregunta dónde guardar y propone el mismo
      nombre del PDF, al lado. Si querés elegirlo antes, usá el botón <strong>💾</strong>.</li>
  <li>Al terminar se habilita <em>"Abrir resultado"</em>, y abajo aparece el
      <strong>informe técnico</strong> con el hash del PDF y de la planilla.</li>
</ol>
<div class="tip">
  💡 El PDF original nunca se modifica. Para empezar con otro archivo, tocá
  <em>"🗑 Limpiar"</em>: deja la solapa como recién abierta y no borra nada del disco.
  Si querés conservar las columnas que marcaste, guardá antes la <strong>receta</strong>.
</div>

<h3>Las páginas: miniaturas y selección</h3>
<ul>
  <li><strong>Un clic</strong> en una miniatura la marca o desmarca (azul = se exporta).
      <strong>Shift + clic</strong> marca un rango entero.</li>
  <li><strong>Doble clic</strong> la abre en el visor.</li>
  <li><em>"De: … a: …"</em> + <em>"Aplicar rango"</em>, <em>"Todas"</em> y <em>"Ninguna"</em>
      hacen lo mismo de una sola vez.</li>
</ul>

<h3>El visor</h3>
<table>
  <tr><th>Qué querés</th><th>Cómo</th></tr>
  <tr><td>Agregar una columna</td><td>Clic izquierdo en el visor: aparece una línea roja.</td></tr>
  <tr><td>Mover una columna</td><td>Arrastrá la línea roja.</td></tr>
  <tr><td>Borrar una columna</td><td>Clic derecho sobre la línea.</td></tr>
  <tr><td>Saltear lo de arriba</td><td><em>"+ Inicio tabla"</em>: línea azul. Todo lo que queda arriba no se lee.</td></tr>
  <tr><td>Saltear lo de abajo</td><td><em>"+ Fin tabla"</em>: línea verde. Si no hay pie de página, no hace falta.</td></tr>
  <tr><td>Acercar o alejar</td><td><code>Ctrl + rueda del mouse</code>. Doble clic en una zona vacía vuelve al tamaño completo.</td></tr>
  <tr><td>Una página distinta a las demás</td><td><em>"Solo esta página:"</em> → <em>"📌 Inicio Y"</em> y <em>"📌 Fin Y"</em> le fijan a esa hoja un inicio y un fin propios. <em>"Quitar"</em> la devuelve a los del grupo.</td></tr>
</table>
<p>
Arriba de la previsualización, la casilla <em>"Sync scroll"</em> hace que la tabla acompañe
al visor cuando te desplazás, para comparar lo que ves en el PDF con lo que va a salir.
<em>"Págs:"</em> indica cuántas páginas se previsualizan, y <strong>↺</strong> la actualiza.
</p>

<h3>¿Qué es un grupo?</h3>
<p>
Un <strong>grupo</strong> es un tramo del PDF que se lee con las mismas columnas. Con uno solo
alcanza casi siempre. Hay hasta cinco (<strong>G1</strong> a <strong>G5</strong>, cada uno con
su color) para cuando el PDF trae tablas distintas, o cuando de la página 1 a la 5 las
columnas están en un lugar y de la 6 en adelante en otro.
</p>
<table>
  <tr><th>Control</th><th>Qué hace</th></tr>
  <tr><td>Casilla <em>"Grupo 1"</em>…</td><td>Lo activa. Sólo los grupos activos se exportan.</td></tr>
  <tr><td><em>"Págs:"</em></td><td>De qué página a qué página vale el grupo.</td></tr>
  <tr><td><em>"Inicio Y"</em> / <em>"Fin Y"</em></td><td>La altura donde empieza y termina la tabla en cada hoja. Se cargan solas con <em>"🔵 Tomar Inicio Y del visor"</em> y <em>"🟢 Tomar Fin Y del visor"</em>.</td></tr>
  <tr><td><em>"Columnas"</em></td><td>La posición de cada línea roja. <em>"🔄 Auto"</em> las detecta; <em>"📐 Tomar del visor"</em> copia las que marcaste a mano.</td></tr>
  <tr><td><em>"↩ Volver"</em></td><td>Deshace el último cambio de ese grupo. Guarda hasta 20 pasos.</td></tr>
  <tr><td><em>"Activar fusión de filas"</em> y <em>"Col. ancla"</em></td><td>Para cuando un movimiento ocupa varios renglones (abajo de la fila principal vienen el nombre, el CBU, el banco). La columna ancla es la que sólo tiene dato en la fila principal —por ejemplo la fecha, columna <code>0</code>—: los renglones que la traen vacía se pegan al de arriba.</td></tr>
  <tr><td><em>"Activar división"</em></td><td>Va junto con la fusión: los renglones que se pegaron en una misma celda pasan a columnas separadas (una descripción de dos renglones queda en Descripción 1 y Descripción 2).</td></tr>
  <tr><td><em>"Corte por palabras clave"</em></td><td>Parte una columna en dos donde aparece una palabra. Ver abajo.</td></tr>
</table>

<h3>Corte por palabras clave</h3>
<p>
En los resúmenes bancarios la columna de descripción suele traer todo junto: el tipo de
operación y el nombre del destinatario
(<code>TRANSFERENCIA DE TERCEROS MOYANO RIVEROS</code>). Con este corte quedan en dos columnas.
</p>
<ol>
  <li>Dentro del grupo, marcá <em>"Corte por palabras clave"</em>.</li>
  <li>En <em>"en col:"</em> poné el número de la columna a partir
      (<code>0</code> = la primera, <code>1</code> = la segunda…).</li>
  <li>Escribí la palabra (por ejemplo <code>TRANSFERENCIA DE TERCEROS</code>) y tocá
      <em>"Agregar"</em>. Repetí con las demás (<code>CREDITO TRANSFERENCIA</code>,
      <code>TRANSFERENCIA</code>…). <em>"Quitar sel."</em> saca la que esté elegida.</li>
  <li>Mirá la previsualización: aparece una columna más, <em>"(resto)"</em>, con lo que
      venía después de la palabra.</li>
</ol>
<div class="tip">
  💡 Las palabras más largas se prueban primero, así <em>"TRANSFERENCIA DE TERCEROS"</em>
  no se corta en <em>"TRANSFERENCIA"</em>. Si un renglón no trae ninguna, queda entero en la
  columna original: no se pierde nada.
</div>

<h3>Cortes de columna en cadena (hasta 9)</h3>
<p>
Para una columna que mezcla varias cosas separadas por un signo
(<code>MOYANO RIVEROS - CBU 000123456 - BANCO GALICIA</code>). Cada solapa numerada del
<strong>1</strong> al <strong>9</strong> es un corte, y cada uno trabaja sobre lo que dejó
el anterior:
</p>
<ol>
  <li>Elegí la columna en el desplegable.</li>
  <li>En <em>"Sep:"</em> escribí el signo que separa (viene <code> - </code>).</li>
  <li>Elegí qué hacer con el signo (<em>"Eliminar sep."</em>, <em>"Unir a Izq."</em> o
      <em>"Unir a Der."</em>) y dónde van las dos columnas nuevas (<em>"Reemplazar"</em> la
      original o <em>"Al final"</em>).</li>
  <li>Poneles nombre en <em>"Izq:"</em> y <em>"Der:"</em> y marcá <em>"Activar"</em>.</li>
</ol>
<div class="tip">
  💡 Atajo: <strong>doble clic en una celda</strong> de la previsualización abre un asistente
  para partir esa columna eligiendo el punto con el mouse.
</div>

<h3>Si el PDF es un escaneo: OCR</h3>
<p>
Si la previsualización sale vacía aunque las líneas estén bien puestas, lo más probable es
que el PDF sea una foto de la hoja y no tenga texto. En la tarjeta
<em>"OCR para páginas imagen (PDF escaneo)"</em>:
</p>
<table>
  <tr><th>Control</th><th>Qué hace</th></tr>
  <tr><td><em>"Activar OCR si no hay texto"</em></td><td>Lee las páginas que son imagen. Las que ya tienen texto se leen como siempre, así que no molesta dejarlo marcado; sólo tarda más (unos segundos por página).</td></tr>
  <tr><td><em>"Idioma"</em></td><td><code>spa+eng</code> (español e inglés) sirve para casi todo.</td></tr>
  <tr><td><em>"Pre-rotar para OCR"</em></td><td>Si la hoja está de cabeza (<code>180°</code>) o acostada (<code>90°</code> o <code>270°</code>). Gira la imagen para leerla y también el visor, así marcás las columnas sobre la hoja derecha. No toca el PDF.</td></tr>
  <tr><td><em>"☀ Fondo blanco"</em> (0 a 10)</td><td>Aclara el fondo. Subilo si la hoja tiene base gris.</td></tr>
  <tr><td><em>"🖋 Texto oscuro"</em> (0 a 10)</td><td>Remarca las letras. Subilo si se ven lavadas o finitas.</td></tr>
  <tr><td><em>"Quitar puntitos"</em></td><td>Borra las motas del escáner, que el OCR confunde con letras sueltas.</td></tr>
  <tr><td><em>"B/N puro"</em></td><td>Blanco y negro sin grises. Es lo más fuerte: para hojas oscuras o muy sucias. Si se come partes de las letras, sacalo.</td></tr>
  <tr><td><em>"Conf:"</em> (10 a 90)</td><td>Cuán segura tiene que estar la lectura para aceptar una palabra. Bajalo a 20–25 si faltan palabras; subilo a 40–50 si aparecen letras de basura.</td></tr>
</table>
<div class="tip">
  💡 Apenas tocás un control de limpieza, <strong>el visor muestra la hoja ya limpia</strong>:
  eso es exactamente lo que va a leer el OCR. Mové un control por vez mirando el visor, como
  quien ajusta el brillo de una foto, hasta ver fondo blanco y letras negras. Un buen punto de
  partida para un escaneo sucio: Fondo blanco <code>3</code>, Texto oscuro <code>2</code>,
  Quitar puntitos marcado y Conf <code>30</code>.
</div>
<table>
  <tr><th>Lo que ves</th><th>Qué tocar</th></tr>
  <tr><td>La hoja tiene base gris o manchas claras</td><td>Fondo blanco 3–5</td></tr>
  <tr><td>Letras grises, finitas o lavadas</td><td>Texto oscuro 2–4</td></tr>
  <tr><td>Puntitos o rayas por toda la hoja</td><td>Quitar puntitos</td></tr>
  <tr><td>Página entera oscura o muy sucia</td><td>B/N puro (más Fondo blanco 2–3)</td></tr>
  <tr><td>Lee poco, faltan palabras</td><td>Conf a 20–25, o limpiar más el fondo</td></tr>
  <tr><td>Celdas con letras de basura (<code>E</code>, <code>7</code>, <code>|</code>)</td><td>Conf a 40–50 y Quitar puntitos</td></tr>
  <tr><td>Números deformados (<code>06</code> sale <code>66</code>)</td><td>Probar B/N puro; si empeora, sólo Fondo y Texto</td></tr>
</table>
<div class="tip">
  💡 El lector de texto (Tesseract) viene con el programa: no hay que instalar nada.
</div>

<h3>Rotar las páginas y guardar un PDF girado</h3>
<p>
La rotación del OCR es sólo para leer. Si además querés quedarte con un PDF derecho, usá la
tarjeta <em>"Rotar páginas PDF"</em>: elegí <em>"Todas las páginas"</em> o
<em>"Solo seleccionadas"</em> (las miniaturas en azul), el ángulo, y tocá
<em>"↻ Rotar y guardar como..."</em>. Guarda un PDF nuevo y te pregunta si querés cargarlo.
</p>

<h3>La tarjeta "Formato Excel"</h3>
<table>
  <tr><th>Opción</th><th>Qué hace</th></tr>
  <tr><td>Filas alternas</td><td>Pinta un renglón por medio, para leer más fácil.</td></tr>
  <tr><td>Bordes</td><td>Le pone bordes finos a las celdas. Útil si vas a imprimir.</td></tr>
  <tr><td>Congelar fila 1</td><td>Los títulos de las columnas quedan fijos al bajar por la planilla.</td></tr>
  <tr><td>Sep. páginas</td><td>Agrega un renglón divisor entre página y página, para saber de qué hoja salió cada dato.</td></tr>
  <tr><td>También PDF</td><td>Además de la planilla, guarda la tabla en un PDF. Lleva el nombre de la planilla; si ese nombre es el del PDF original, se llama <em>…_tabla.pdf</em> para no pisarlo.</td></tr>
  <tr><td>Esp. palabras</td><td>Cuánto espacio hace falta entre letras para considerarlas palabras distintas. Bajalo (8 o 10) si salen pegadas; subilo si salen partidas.</td></tr>
  <tr><td>Ignorar margen izq.</td><td>Descarta lo que esté pegado al borde izquierdo de la hoja (números de página, códigos sueltos).</td></tr>
</table>

<h3>La receta: no marcar todo de nuevo</h3>
<p>
Si todos los meses te llega el mismo resumen, marcá las columnas una vez y tocá
<em>"Guardar receta"</em>: queda un archivo <code>.json</code> con los grupos, las columnas y
las opciones. La próxima vez cargás el PDF, tocás <em>"Cargar receta"</em> y está todo listo.
</p>

<h3>Abrir una planilla que ya tenés</h3>
<p>
El mismo botón <em>"📂 Cargar Fuente de Datos"</em> acepta <code>.xlsx</code>,
<code>.csv</code> y <code>.ods</code>. En ese caso no hay nada que marcar: se abre en la
solapa <em>"Editor Excel/CSV"</em>, donde podés corregir celdas, <em>"💾 Guardar cambios"</em>
o <em>"📥 Exportar como xlsx"</em>.
</p>
<div class="warn">
  ⚠️ El Excel viejo (<code>.xls</code>) no se abre acá. Abrilo en Excel o LibreOffice,
  guardalo como <code>.xlsx</code> y cargá ese.
</div>

<h3>Si algo no sale bien</h3>
<table>
  <tr><th>Qué pasa</th><th>Qué hacer</th></tr>
  <tr><td>Las palabras salen pegadas (<code>TRANSFERENCIADETERCEROS</code>)</td><td>Bajá <em>"Esp. palabras"</em> a 8 o 10.</td></tr>
  <tr><td>Aparecen números sueltos en la primera columna</td><td>Marcá <em>"Ignorar margen izq."</em>.</td></tr>
  <tr><td>Un movimiento sale repartido en 4 o 5 filas</td><td><em>"Activar fusión de filas"</em>, con la columna de la fecha como ancla.</td></tr>
  <tr><td><em>"🔄 Auto"</em> no encuentra todas las columnas</td><td>Agregá las que faltan con un clic en el visor. Lo automático es un punto de partida.</td></tr>
  <tr><td>La previsualización sale vacía</td><td>El PDF es un escaneo: marcá <em>"Activar OCR si no hay texto"</em>.</td></tr>
  <tr><td>El escaneo está de cabeza o de costado</td><td><em>"Pre-rotar para OCR"</em>.</td></tr>
  <tr><td>Tarda mucho</td><td>Es normal con PDF de 200 páginas o más (entre medio minuto y un minuto y medio), y bastante más con OCR. La barra y el registro de abajo muestran por dónde va.</td></tr>
  <tr><td>Dice que no tiene permiso para guardar</td><td>La planilla está abierta en Excel: cerrala y volvé a convertir.</td></tr>
</table>

<hr class="section-sep">

<!-- ─── 8 ─── -->
<h2>8. 📄 Documentos</h2>
<table>
  <tr><th>Formato</th><th>Para qué sirve</th></tr>
  <tr><td>PDF</td><td>Documento universal. Se ve igual en todas las computadoras.</td></tr>
  <tr><td>DOCX</td><td>Documento de Word. Editable con Microsoft Office o LibreOffice.</td></tr>
  <tr><td>ODT</td><td>Documento de LibreOffice. Formato abierto.</td></tr>
  <tr><td>TXT</td><td>Texto plano. Sin formato, compatible con todo.</td></tr>
  <tr><td>EPUB</td><td>Libro digital. Compatible con lectores de e-books y tablets.</td></tr>
  <tr><td>HTML</td><td>Página web. Se abre en el navegador.</td></tr>
  <tr><td>RTF</td><td>Texto con formato básico. Compatible con editores viejos.</td></tr>
  <tr><td>MD</td><td>Markdown. Texto con formato simple para programadores y documentación.</td></tr>
  <tr><td>PAGES</td><td>Documento de Apple Pages (Mac/iPhone). Convertilo a PDF o DOCX para abrirlo en Windows.</td></tr>
  <tr><td>KEY</td><td>Presentación de Apple Keynote. Convertila a PDF o PPTX.</td></tr>
  <tr><td>NUMBERS</td><td>Planilla de Apple Numbers. Convertila a XLSX, CSV o PDF.</td></tr>
  <tr><td>WPS</td><td>Documento de Kingsoft/WPS Office. Convertilo a DOCX o PDF.</td></tr>
</table>
<div class="tip">
  💡 <strong>Todo lo que es texto se convierte a cualquier otro formato de texto.</strong>
  No hace falta buscar la combinación en una lista: si cargás un DOCX, un ODT, un PDF,
  un EPUB, un HTML, un MD o un TXT, la grilla te muestra todos los destinos posibles.
  Cuando no existe un paso directo, el programa arma la cadena solo (por ejemplo
  RTF → DOCX → MD) y te lo avisa con el ícono 🔗 en el botón del formato.
</div>
<div class="tip">
  💡 Un documento también puede salir como <strong>imágenes</strong>: elegí PNG o JPG
  y obtenés una foto por página. Al revés no: para sacar el texto de una foto se usa
  el OCR (sección 10).
</div>
<div class="tip">
  💡 Los formatos de Apple (PAGES, KEY, NUMBERS) y WPS requieren tener LibreOffice instalado.
</div>

<hr class="section-sep">

<!-- ─── 9 ─── -->
<h2>9. 📊 Datos estructurados</h2>
<table>
  <tr><th>Formato</th><th>Para qué sirve</th></tr>
  <tr><td>CSV</td><td>Tabla en texto plano. Abrila con Excel o cualquier planilla.</td></tr>
  <tr><td>XLSX</td><td>Planilla de Excel. Ideal para compartir datos tabulares.</td></tr>
  <tr><td>JSON</td><td>Formato de datos para sistemas y programas.</td></tr>
  <tr><td>XML</td><td>Datos estructurados. Usado en sistemas gubernamentales y legacy.</td></tr>
  <tr><td>YAML</td><td>Configuraciones y datos en formato legible para humanos.</td></tr>
</table>
<div class="tip">
  💡 Si tenés una planilla con múltiples hojas, el programa te pregunta si querés un archivo por hoja o todo junto.
</div>

<h3>Otros formatos soportados</h3>
<table>
  <tr><th>Tipo</th><th>Conversiones</th></tr>
  <tr><td>PDF → Word</td><td>PDF → DOCX conservando el diseño (tablas, columnas, imágenes).</td></tr>
  <tr><td>Subtítulos</td><td>SRT, VTT, ASS y SUB entre sí, en cualquier sentido. Además a TXT (la transcripción sin tiempos), y de ahí a MD, PDF o DOCX.</td></tr>
  <tr><td>Fuentes</td><td>TTF, OTF, WOFF, WOFF2 (tipografías para web y escritorio).</td></tr>
  <tr><td>Comprimidos</td><td>ZIP ↔ TAR, ZIP ↔ 7Z, TAR ↔ GZ, RAR → ZIP (leer RAR requiere WinRAR/UnRAR).</td></tr>
  <tr><td>Ebooks</td><td>EPUB → PDF, MOBI/AZW3 → EPUB, PDF → EPUB. Crear MOBI/AZW3 requiere Calibre instalado.</td></tr>
  <tr><td>Vectorial</td><td>SVG → PNG/JPG/PDF/EPS, PDF → SVG, AI → PDF/PNG. EPS de origen requiere Ghostscript.</td></tr>
  <tr><td>Diseño</td><td>PSD (Photoshop) → PNG/JPG/PDF, DNG (RAW) → JPG/PNG.</td></tr>
  <tr><td>Notebooks</td><td>IPYNB (Jupyter) → HTML/PDF, RST → HTML/PDF, TEX → HTML/PDF.</td></tr>
</table>

<hr class="section-sep">

<!-- ─── 10 ─── -->
<h2>10. 🔍 Reconocimiento de texto (OCR)</h2>
<p>
El OCR (Optical Character Recognition) "lee" el texto que aparece en imágenes y PDFs escaneados.
</p>
<p>Por ejemplo, si tenés un PDF que es una foto de un documento (no se puede seleccionar el texto),
el OCR puede extraer ese texto y convertirlo en un documento editable.</p>

<h3>Dos formas de salida</h3>
<table>
  <tr><th>Salida</th><th>Qué obtenés</th></tr>
  <tr><td><strong>PDF buscable</strong> (a PDF)</td><td>Conserva la página original tal cual y le agrega por debajo una capa de texto invisible. El documento se ve idéntico al escaneo, pero el texto se puede <strong>seleccionar y buscar con Ctrl+F</strong>. Ideal para libros y expedientes escaneados.</td></tr>
  <tr><td><strong>Texto plano</strong> (a TXT)</td><td>Extrae solo el texto, sin formato ni imágenes, con marcadores <code>--- Página N ---</code>. Útil para copiar/pegar o editar el contenido.</td></tr>
</table>
<h3>Cómo hacerlo, paso a paso (la forma más simple)</h3>
<ol>
  <li>En la barra lateral izquierda, entrá a <strong>📄 PDF</strong>.</li>
  <li>Elegí la solapa <strong>"🔍 Reconocer texto"</strong>.</li>
  <li>Tocá <em>"📄 Elegir PDF..."</em> y buscá el archivo escaneado.</li>
  <li>Fijate en el <strong>cartel de color</strong> que aparece:
    <ul>
      <li><strong>Verde</strong> → "Este PDF parece escaneado": el OCR le sirve, seguí.</li>
      <li><strong>Celeste</strong> → "Este PDF ya tiene texto buscable": no hace falta.
          Podés hacerlo igual, pero vas a esperar sin ganar nada.</li>
    </ul>
  </li>
  <li>Elegí qué querés obtener:
    <ul>
      <li><strong>"Un PDF igual al original, pero con el texto buscable"</strong> — la opción
          recomendada. El documento se ve idéntico y además se puede buscar con Ctrl+F.</li>
      <li><strong>"Un archivo de texto (.txt)"</strong> — sólo las palabras, sin diseño.</li>
    </ul>
  </li>
  <li>El <strong>idioma</strong> ya viene en <em>Español</em>: no lo toques salvo que el
      documento esté en otro idioma. Si querés que pese menos, marcá
      <em>"Blanco y negro"</em>.</li>
  <li>Tocá <em>"🔍 Reconocer el texto"</em> y elegí dónde guardarlo. Listo.</li>
</ol>

<h3>La otra forma: durante una conversión</h3>
<p>
Si además de reconocer el texto querés <strong>cambiar de formato</strong> (por ejemplo,
un escaneo en JPG que tiene que terminar en Word), hacelo desde
<strong>🔄 Convertir</strong>: cargá el archivo, activá la opción
<em>"Reconocer texto (OCR)"</em> y elegí el formato de salida.
</p>

<h3>Qué archivos puede leer el OCR</h3>
<p>
El OCR trabaja sobre <strong>páginas que son imágenes</strong>. Acepta como entrada:
</p>
<table>
  <tr><th>Entrada</th><th>Detalle</th></tr>
  <tr><td>PDF escaneado</td><td>El caso más común: cada página es una foto del papel.</td></tr>
  <tr><td>Fotos y escaneos sueltos</td><td>JPG, PNG, TIFF, BMP y demás formatos de imagen.</td></tr>
</table>
<div class="tip">
  💡 Los documentos que <strong>ya son texto</strong> (DOCX, ODT, TXT, RTF, EPUB, PAGES…)
  no necesitan OCR: su texto ya se puede buscar y copiar. Para pasar de uno a otro usá
  <strong>🔄 Convertir</strong>; la lista completa está en la sección
  <em>"8. 📄 Documentos"</em> de este manual.
</div>
<div class="warn">
  ⚠️ Para que funcione, debe estar instalado <code>tesseract.exe</code> (en la carpeta <code>bin/</code> del programa o en la instalación estándar de Windows). Si falta, la solapa te lo avisa en un cartel naranja.
</div>
<div class="tip">
  💡 Los libros y PDF grandes (cientos de páginas) tardan varios minutos: el programa procesa una página por vez
  y la barra avanza a medida que las completa. No cierres el programa mientras trabaja.
</div>
<div class="warn">
  ⚠️ El OCR <strong>nunca es perfecto</strong>. Con un escaneo nítido y derecho acierta casi
  todo; con letra manuscrita, sellos, fotocopias grises o páginas torcidas se equivoca.
  Revisá siempre el resultado antes de usarlo como texto oficial.
</div>

<hr class="section-sep">

<!-- ─── 11 ─── -->
<h2>11. 💧 Marca de agua y leyenda</h2>
<p><strong>Marca de agua:</strong> Texto diagonal semitransparente que aparece sobre el contenido. Ejemplo: "CONFIDENCIAL", "BORRADOR", "COPIA".</p>
<p><strong>Leyenda al pie:</strong> Texto pequeño centrado en el margen inferior de cada página. Ejemplo: "Ministerio de Salud · Uso Interno".</p>

<h3>Cómo agregarlas</h3>
<p>
Son <strong>opciones de la conversión</strong>: se aplican mientras el archivo se convierte
a PDF, no después.
</p>
<ol>
  <li>Barra lateral → <strong>🔄 Convertir</strong>.</li>
  <li>Agregá el archivo y elegí <strong>PDF</strong> como formato de salida.</li>
  <li>En el panel de opciones, tocá <em>"💧 Agregar marca de agua"</em> o
      <em>"✏️ Leyenda al pie de página"</em> para desplegarlas, y marcá la casilla.</li>
  <li>Escribí el texto y, si querés, elegí el color.</li>
  <li>Tocá <em>"🚀 CONVERTIR"</em>.</li>
</ol>
<div class="warn">
  ⚠️ Sólo funcionan cuando el formato de salida es <strong>PDF</strong>. Si elegís otro
  formato, la opción no tiene efecto.
</div>

<hr class="section-sep">

<!-- ─── 12 ─── -->
<h2>12. 🔢 Numeración de páginas</h2>
<p>Agrega números de página automáticos al convertir a PDF.</p>

<h3>Cómo hacerlo</h3>
<ol>
  <li>Barra lateral → <strong>🔄 Convertir</strong>, agregá el archivo y elegí
      <strong>PDF</strong> como salida.</li>
  <li>Desplegá la opción <em>"🔢 Numerar páginas"</em> y marcala.</li>
  <li>Elegí la <strong>posición</strong>: centro, derecha o izquierda, arriba o abajo.</li>
  <li>Elegí el <strong>formato</strong> del número:
    <ul>
      <li><code>Página {n} de {total}</code> → "Página 3 de 10"</li>
      <li><code>{n}</code> → "3"</li>
      <li><code>- {n} -</code> → "- 3 -"</li>
    </ul>
  </li>
  <li>Tocá <em>"🚀 CONVERTIR"</em>.</li>
</ol>
<div class="tip">
  💡 Para foliar un documento que <strong>ya es PDF</strong>, convertilo de PDF a PDF con
  esta opción activada: el resultado es el mismo documento, numerado.
</div>

<hr class="section-sep">

<!-- ─── 12b ─── -->
<h2>12b. 📑 Los números de página, para poder citar</h2>
<p>
Un archivo de texto <strong>no tiene páginas</strong>: es un chorro continuo. Eso se
vuelve un problema cuando el documento se usa como fuente. Si convertís un libro o un
documento a Markdown y después le pedís a una IA que te resuma algo o que te busque
una cita, no va a poder decirte de qué hoja salió, simplemente porque en el archivo esa
información ya no existe.
</p>
<p>
Por eso, al convertir a texto el programa <strong>intercala el número de página</strong>
del documento original, en un renglón aparte:
</p>
<table>
  <tr><th>En el archivo convertido vas a ver</th></tr>
  <tr><td><code>--- [PÁGINA 7] ---</code></td></tr>
</table>
<p>
Va solo, con un renglón en blanco antes y después, para que ningún programa lo pegue al
párrafo de al lado. Con eso, la IA (o vos con Ctrl+F) puede citar
<em>«esto está en la página 7»</em>.
</p>
<h3>De dónde salen esos números</h3>
<table>
  <tr><th>Origen</th><th>Cómo se obtiene la página</th></tr>
  <tr><td><strong>PDF</strong></td><td>Directo: el PDF ya está paginado, cada hoja es una hoja.</td></tr>
  <tr><td><strong>Word y ODT</strong></td><td>Del corte de página que el procesador de texto dejó anotado
      la última vez que mostró el documento. Es la misma paginación que ves al abrirlo o al imprimirlo.</td></tr>
</table>
<div class="tip">
  💡 Si un párrafo empieza en una hoja y termina en la otra, se cuenta en la hoja
  <strong>donde empezó</strong>, que es como se cita. El párrafo no se corta al medio.
</div>
<div class="warn">
  ⚠️ Hay documentos que <strong>no tienen información de páginas</strong>: los que nunca
  pasaron por un procesador de texto (por ejemplo, un .odt generado por otro programa).
  En ese caso el conversor <strong>no inventa números</strong>: hace la conversión sin
  marcadores. Si necesitás las páginas de un documento así, abrilo y guardalo una vez
  con LibreOffice o Word, y volvé a convertirlo.
</div>
<div class="tip">
  💡 Se puede apagar: en <strong>🔄 Convertir</strong>, la opción
  <em>"📑 Marcar los números de página (para poder citar)"</em>. Viene activada.
  Apagala si querés el texto corrido, sin ninguna marca.
</div>

<hr class="section-sep">

<!-- ─── 13 ─── -->
<h2>13. 🕵️ Eliminar metadatos</h2>
<p>
Los metadatos son información "invisible" que los archivos llevan consigo: quién los creó, cuándo, con qué dispositivo, desde qué ubicación GPS, etc.
</p>

<h3>Cómo controlarlo</h3>
<ol>
  <li>Barra lateral → <strong>🔄 Convertir</strong>.</li>
  <li>Buscá la opción <em>"🕵️ Eliminar metadatos del archivo de salida"</em>.
      <strong>Ya viene activada</strong>: si no la tocás, los archivos convertidos salen
      limpios.</li>
  <li>Desmarcala sólo si necesitás <strong>conservar</strong> esos datos —por ejemplo,
      cuando la fecha de creación o la ubicación GPS de una foto son parte de la prueba.</li>
</ol>
<div class="tip">
  ✅ Dejala activada para documentos oficiales o que se comparten externamente.
</div>
<div class="warn">
  ⚠️ Ojo en pericias: si los metadatos son parte de lo que hay que probar,
  <strong>desmarcá la opción</strong> o trabajá siempre sobre el archivo original,
  porque el convertido ya no los va a tener.
</div>

<hr class="section-sep">

<!-- ─── 14 ─── -->
<h2>14. 📋 La constancia de conversión</h2>
<p>
Cada vez que convertís un archivo, el programa genera una <strong>constancia</strong> que incluye:
</p>
<ul>
  <li>El nombre del archivo original y del convertido</li>
  <li>Los tamaños de ambos archivos</li>
  <li>Los códigos SHA-256 y MD5 (huellas digitales únicas del archivo)</li>
  <li>La fecha y hora de la conversión</li>
  <li>El resultado (exitoso o fallido)</li>
</ul>
<h3>Cómo verla y usarla</h3>
<ol>
  <li>Convertí el archivo normalmente desde <strong>🔄 Convertir</strong>.</li>
  <li>Cuando termine, andá a la barra lateral → <strong>📋 Log</strong>.</li>
  <li>Ahí está la constancia de cada archivo de la sesión.</li>
  <li>Tocá <em>"📋 Copiar constancia"</em> y pegala en tu escrito, o guardala como
      archivo de texto para adjuntarla donde la necesites.</li>
</ol>
<p>
Sirve para acreditar que el archivo se convirtió sin alteraciones: quien reciba el
archivo puede recalcular su hash y comprobar que es el mismo que figura en la constancia.
</p>
<div class="tip">
  💡 La constancia usa <strong>SHA-256 y MD5</strong>. Si necesitás una huella más fuerte
  o verificar un archivo contra un hash que te pasaron, usá el módulo
  <strong>🔢 Extraer hash</strong> (ver la sección siguiente).
</div>
<div class="tip">
  💡 Las operaciones del módulo <strong>📄 PDF</strong> (unir, partir, firmar, OCR) no
  usan esta constancia: generan su propio <strong>informe técnico</strong>, que aparece
  al pie de la pantalla y explica en prosa qué se hizo con cada archivo.
</div>

<h3>🗂 Historial de sesiones: ver y eliminar</h3>
<p>
En el panel <strong>"📋 Log y constancias"</strong>, la pestaña <strong>"📁 Historial"</strong> guarda un registro de cada sesión de conversión. Desde ahí podés:
</p>
<ul>
  <li><strong>📂 Abrir sesión:</strong> ver las constancias de una sesión anterior.</li>
  <li><strong>🗑 Eliminar seleccionados:</strong> borrar solo las sesiones que elijas (con <em>Ctrl+clic</em> o <em>Shift+clic</em> podés seleccionar varias).</li>
  <li><strong>🗑 Eliminar todos:</strong> borrar el historial completo.</li>
</ul>
<p>
Ambas opciones piden confirmación antes de borrar. Eliminar el historial <strong>no toca los archivos convertidos</strong>: solo borra los registros.
</p>

<hr class="section-sep">

<!-- ─── 14b ─── -->
<h2>14b. 🔢 El hash y el informe técnico</h2>

<h3>¿Qué es un hash y para qué sirve?</h3>
<p>
El <strong>hash</strong> es la <strong>huella digital</strong> de un archivo: un código
largo de números y letras que se calcula a partir de su contenido. Tiene dos propiedades
que lo hacen útil:
</p>
<ul>
  <li>El <strong>mismo archivo</strong> da <strong>siempre el mismo código</strong>, en
      esta computadora o en cualquier otra.</li>
  <li>Si se modifica <strong>un solo byte</strong> —una coma, un píxel— el código cambia
      por completo.</li>
</ul>
<p>
Por eso sirve para <strong>probar que un archivo no fue alterado</strong>. Si entregás un
archivo digital junto con su hash, cualquiera puede recalcularlo más tarde: si da igual,
el archivo es idéntico al que entregaste; si da distinto, alguien lo tocó.
</p>
<div class="tip">
  💡 No es una contraseña ni un cifrado: el hash <strong>no oculta</strong> el contenido y
  no se puede "revertir" para recuperar el archivo. Sólo sirve para comparar.
</div>

<h3>Cómo sacar el hash de un archivo</h3>
<ol>
  <li>En la barra lateral izquierda, entrá a <strong>🔢 Extraer hash</strong>.</li>
  <li>Tocá <em>"➕ Agregar archivos..."</em> (o <em>"📁 Agregar carpeta..."</em> para
      sacarle el hash a todo lo que haya adentro). Sirve para
      <strong>cualquier tipo de archivo</strong>, no sólo PDF: videos, audios, fotos, planillas.</li>
  <li>Dejá marcados <strong>SHA-256</strong> y <strong>SHA-512</strong>, que vienen por
      defecto.</li>
  <li>Tocá <em>"🔢 Calcular los hashes"</em>.</li>
  <li>Con <em>"📋 Copiar"</em> lo pegás en un escrito, y con
      <em>"💾 Guardar como informe..."</em> generás un archivo de texto listo para adjuntar.</li>
</ol>

<h3>Cómo verificar que un archivo es el correcto</h3>
<p>
Si alguien te pasó un archivo <strong>y su hash</strong>, podés comprobar que no se haya
alterado en el camino:
</p>
<ol>
  <li>Entrá a <strong>🔢 Extraer hash</strong> y agregá el archivo recibido.</li>
  <li>En el recuadro <strong>"🔎 ¿Te pasaron un hash? Verificá el archivo"</strong>,
      pegá el código que te dieron.</li>
  <li>Tocá <em>"🔎 Verificar"</em>.</li>
</ol>
<p>
No necesitás saber de qué tipo es el código: el programa <strong>lo reconoce solo</strong>
por su longitud y lo calcula aunque no lo hayas marcado arriba. La respuesta es directa:
<strong>✅ COINCIDE</strong> (es idéntico, no fue modificado) o
<strong>❌ NO COINCIDE</strong> (no es el mismo archivo, o fue alterado).
</p>

<h3>¿Por qué SHA-256 y SHA-512, y no SHA-1 o MD5?</h3>
<table>
  <tr><th>Algoritmo</th><th>Estado</th></tr>
  <tr><td><strong>SHA-256</strong></td><td>El estándar actual. Es el que más se usa para verificar integridad.</td></tr>
  <tr><td><strong>SHA-512</strong></td><td>Más largo, misma familia. Va como segundo respaldo.</td></tr>
  <tr><td>SHA3-256 · BLAKE2b</td><td>Igual de seguros, de familias distintas. Opcionales.</td></tr>
  <tr><td>SHA-1 · MD5</td><td><strong>Obsoletos.</strong> Se demostró que se pueden fabricar dos archivos distintos con el mismo código, así que ya no prueban nada. Están disponibles sólo porque algunos sistemas viejos los exigen.</td></tr>
</table>
<div class="warn">
  ⚠️ Si un organismo te pide un MD5 o un SHA-1, dáselo, pero acompañalo siempre de un
  SHA-256. El obsoleto solo no alcanza como garantía.
</div>

<h3>El informe técnico</h3>
<p>
Cuando el programa hace algo con tus archivos —unir, partir, firmar, reconocer texto—
genera abajo un <strong>informe técnico</strong>. No es un adorno: es la constancia de qué
se hizo y con qué archivos.
</p>
<p>El informe dice, para cada operación:</p>
<ul>
  <li><strong>Qué se hizo</strong>, redactado en prosa. Por ejemplo:
      <em>"Se procedió a partir el archivo «informe.pdf» en partes de hasta 10 MB
      cada una"</em>.</li>
  <li><strong>El archivo original</strong>, con su tamaño y sus hashes.</li>
  <li><strong>Cada archivo resultante</strong>, con su tamaño y sus hashes. Si se generaron
      varias partes, aparecen todas, numeradas.</li>
  <li>La <strong>fecha</strong> de la operación.</li>
</ul>
<p>
Con eso, quien reciba los archivos puede verificar uno por uno que son exactamente los que
salieron de este programa. Debajo del informe tenés botones para
<strong>copiarlo</strong> o <strong>guardarlo</strong> como archivo de texto.
</p>
<div class="tip">
  💡 El informe aparece recién <strong>después</strong> de completar una operación, al pie
  del módulo. Si no lo ves, es que todavía no ejecutaste nada en esa pantalla.
</div>

<hr class="section-sep">

<!-- ─── 15 ─── -->
<h2>15. ⚠️ ¿Por qué un botón está gris o con ⛔?</h2>
<ul>
  <li><strong>Botón gris:</strong> La función no está disponible en este momento. Por ejemplo, "CONVERTIR" aparece gris si no agregaste archivos todavía.</li>
  <li><strong>⛔ en un archivo:</strong> Ese archivo no se puede convertir al formato elegido, o supera el límite de tamaño.</li>
  <li><strong>⚠️ Naranja:</strong> Una función opcional no está disponible (por ejemplo, FFmpeg no encontrado para audio/video).</li>
</ul>

<hr class="section-sep">

<!-- ─── 16 ─── -->
<h2>16. 🗑 El botón "Limpiar todo"</h2>
<p>
Este botón detiene todas las conversiones en curso y vacía la lista de archivos.
</p>
<div class="warn">
  ⚠️ <strong>Los archivos que ya se convirtieron NO se borran</strong>. Solo se limpia la pantalla para empezar de nuevo.
</div>
<p>Usalo cuando:</p>
<ul>
  <li>Metiste los archivos equivocados</li>
  <li>Querés empezar con una conversión diferente</li>
  <li>El programa se "trabó" y querés reiniciar la cola</li>
</ul>
<p>
En el resto del programa pasa lo mismo: <strong>cada solapa de trabajo</strong> (las de
PDF, Audio, Video, Tablas, hash) tiene su botón <em>"🗑 Limpiar"</em>. Saca el archivo
que habías elegido, esconde el informe del trabajo anterior y deja la solapa como
recién abierta, para seguir con otro archivo o volver a cargar el mismo. Tampoco
borra nada de lo que ya guardaste.
</p>

<hr class="section-sep">

<!-- ─── 17 ─── -->
<h2>17. ❓ Preguntas frecuentes</h2>

<h3>¿Puedo convertir varios archivos a la vez?</h3>
<p>Sí. Podés agregar tantos archivos como quieras. El programa los convierte de a dos en paralelo para no sobrecargar la computadora.</p>

<h3>¿El archivo original se borra?</h3>
<p>No. El programa crea un archivo nuevo. El original queda intacto.</p>

<h3>¿Qué pasa si el archivo ya existe en la carpeta de destino?</h3>
<p>El programa te pregunta si querés reemplazarlo o saltearlo.</p>

<h3>¿Por qué no aparece el formato que necesito?</h3>
<p>El selector solo muestra los formatos a los que se puede convertir desde los archivos que cargaste. Si lo que no aparece es un formato de documento (Word, Excel, PowerPoint, OpenDocument), es porque esa computadora no tiene instalado <strong>LibreOffice</strong> ni Microsoft Office: es lo único que el programa toma de la computadora en vez de traerlo adentro. LibreOffice es gratuito.</p>

<h3>¿Funciona sin internet?</h3>
<p>Sí, totalmente. Los subtítulos automáticos, la solapa <strong>"🎙 Transcribir"</strong>,
y el OCR no descargan nada: usan lo que viene en la carpeta del programa.</p>

<h3>¿Puedo llevar el programa a otra computadora?</h3>
<p>Sí. Copiá la <strong>carpeta entera</strong> (no sólo el archivo .exe) a un pendrive o
a un disco, y abrilo desde ahí. No hay que instalar nada. Para transcribir alcanza con
el procesador; en una computadora con poca memoria el programa elige solo el modelo
<em>Chico</em>.</p>

<h3>El programa tardó mucho en un archivo grande. ¿Es normal?</h3>
<p>Sí. Los videos y archivos de audio pesados pueden tardar varios minutos. Mientras trabaja, podés seguir usando la computadora normalmente.</p>

</body>
</html>
"""
