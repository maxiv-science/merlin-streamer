from merlin import Merlin, print_color
from sanic import Sanic, response

def print(msg):
    print_color('server: %s' % msg, 'green')

app = Sanic(name='Merlin Server')
merlin = None

@app.listener('before_server_start')
async def start(app, loop):
    global merlin
    merlin = Merlin('172.16.126.78', debug=True)


@app.route('/arm', methods=['PUT'])
def put_arm(request):
    print('entering put_arm')
    merlin.arm()
    return response.text('')
    print('leaving put_arm')


@app.route('/start', methods=['PUT'])
async def put_start(request):
    print('entering put_start')
    nframes = request.json['value']
    await merlin.start(nframes)
    return response.text('')
    print('leaving put_start')


@app.route('/stop', methods=['PUT'])
def put_stop(request):
    print('stop')
    merlin.stop()
    return response.text('')


@app.route('/filename', methods=['PUT'])
def put_filename(request):
    filename = request.json['value']
    merlin.filename = filename
    return response.text('')


@app.route('/energy')
def get_energy(request):
    value = float(merlin.get(b'OPERATINGENERGY'))
    return response.json({'value': value})

@app.route('/energy', methods=['PUT'])
def put_energy(request):
    value = request.json['value']
    merlin.set(b'OPERATINGENERGY', value)
    return response.text('')


@app.route('/trigger_start')
def get_trigger_start(request):
    value = int(merlin.get(b'TRIGGERSTART'))
    return response.json({'value': value})

@app.route('/trigger_start', methods=['PUT'])
def put_trigger_start(request):
    value = request.json['value']
    merlin.set(b'TRIGGERSTART', value)
    return response.text('')


@app.route('/acquisition_time')
def get_acquisition_time(request):
    value = float(merlin.get(b'ACQUISITIONTIME'))
    return response.json({'value': value})

@app.route('/acquisition_time', methods=['PUT'])
def put_acquisition_time(request):
    value = request.json['value']
    merlin.set(b'ACQUISITIONTIME', value)
    return response.text('')


@app.route('/acquisition_period')
def get_acquisition_period(request):
    value = float(merlin.get(b'ACQUISITIONPERIOD'))
    return response.json({'value': value})

@app.route('/acquisition_period', methods=['PUT'])
def put_acquisition_period(request):
    value = request.json['value']
    merlin.set(b'ACQUISITIONPERIOD', value)
    return response.text('')


@app.route('/num_frames')
def get_num_frames(request):
    value = int(merlin.get(b'NUMFRAMESTOACQUIRE'))
    return response.json({'value': value})

@app.route('/num_frames', methods=['PUT'])
def put_num_frames(request):
    value = request.json['value']
    merlin.set(b'NUMFRAMESTOACQUIRE', value)
    return response.text('')

   
@app.route('/num_frames_per_trigger', methods=['GET'])
def get_num_frames_per_trigger(request):
    nframes = int(merlin.get(b'NUMFRAMESPERTRIGGER'))
    return response.json({'value': nframes})
   
@app.route('/num_frames_per_trigger', methods=['PUT'])
def put_num_frames_per_trigger(request):
    value = request.json['value']
    merlin.set(b'NUMFRAMESPERTRIGGER', value)
    return response.text('')

@app.route('/continuousrw', methods=['GET'])
def get_continuousrw(request):
    gapless = bool(int(merlin.get(b'CONTINUOUSRW')))
    return response.json({'value': gapless})

@app.route('/continuousrw', methods=['PUT'])
def put_continuousrw(request):
    value = request.json['value']
    merlin.set(b'CONTINUOUSRW', int(value))
    return response.text('')

@app.route('/counterdepth', methods=['GET'])
def get_counterdepth(request):
    depth = int(merlin.get(b'COUNTERDEPTH'))
    return response.json({'value': depth})

@app.route('/counterdepth', methods=['PUT'])
def put_counterdepth(request):
    value = request.json['value']
    merlin.set(b'COUNTERDEPTH', value)
    return response.text('')

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=8000, workers=1, access_log=False, debug=True)
    except KeyboardInterrupt:
        merlin.process.terminate()
