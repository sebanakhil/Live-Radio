import asyncio
import json
from aiohttp import web
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaRelay

# Global State
pcs = set()
relay = MediaRelay()
broadcaster_track = None
CHANNEL_NAME = "Gemini Live Radio 📻"

# STUN servers help bypass firewalls
configuration = RTCConfiguration(
    iceServers=[RTCIceServer(urls=["stun:stun.l.google.com:19302"])]
)

async def status(request):
    """Returns the current state of the broadcast for listeners."""
    return web.json_response({
        "is_live": broadcaster_track is not None,
        "channel_name": CHANNEL_NAME if broadcaster_track else None,
        "listener_count": len([pc for pc in pcs if pc.getTransceivers() and any(t.direction == "sendonly" for t in pc.getTransceivers())])
    })

async def offer(request):
    global broadcaster_track
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    role = params.get("role")

    pc = RTCPeerConnection(configuration=configuration)
    pcs.add(pc)
    # 2. PLACE THE PORT FIX HERE (Before the handshake)
    try:
        # We ensure a transceiver exists so the gatherer is initialized
        if not pc.getTransceivers():
            pc.addTransceiver("audio") 
        
        # Access the internal ice_gatherer to force the port range
        pc._ice_gatherer._port_range = (10000, 10005)
        print(f"DEBUG: Forced port range (10000-10005) for {role}")
    except Exception as e:
        print(f"DEBUG: Failed to set port range for {role}: {e}")



    @pc.on("iceconnectionstatechange")
    async def on_state_change():
        if pc.iceConnectionState in ["failed", "closed"]:
            await pc.close()
            pcs.discard(pc)
            # If the broadcaster leaves, reset the global track
            if role == "broadcaster":
                global broadcaster_track
                broadcaster_track = None
                print("⚠️ Broadcaster disconnected. Channel is offline.")

    @pc.on("track")
    def on_track(track):
        global broadcaster_track
        if role == "broadcaster" and track.kind == "audio":
            # Wrap the incoming track in a relay for multiple listeners
            broadcaster_track = relay.subscribe(track)
            print(f"📡 {CHANNEL_NAME} is now LIVE!")

    # Logic for Listeners joining
    if role == "listener":
        if broadcaster_track:
            pc.addTrack(broadcaster_track)
        else:
            return web.json_response({"error": "Channel not live"}, status=400)

    # Signaling handshake
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.json_response({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })

async def index(request):
    return web.FileResponse("./static/index.html")

async def on_shutdown(app):
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

app = web.Application()
app.on_shutdown.append(on_shutdown)
app.router.add_get("/", index)
app.router.add_get("/status", status)
app.router.add_post("/offer", offer)
app.router.add_static("/static/", path="./static")

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8080)