using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Globalization;
using UnityEngine;

public class HypeReceiver : MonoBehaviour
{
    [Header("Network")]
    public int port = 5005;

    [Header("Live Data (read-only at runtime)")]
    public float hypeScore;

    private UdpClient _udpClient;
    private Thread _listenThread;
    private volatile bool _running;
    private volatile float _latestScore;

    private void Start()
    {
        _running = true;
        _listenThread = new Thread(Listen)
        {
            IsBackground = true,
            Name = "HypeUDPListener"
        };
        _listenThread.Start();
    }

    private void Update()
    {
        hypeScore = _latestScore;
    }

    private void Listen()
    {
        try
        {
            _udpClient = new UdpClient(port);
        }
        catch (SocketException e)
        {
            Debug.LogError($"[HypeReceiver] Could not bind to port {port}: {e.Message}");
            return;
        }

        var endPoint = new IPEndPoint(IPAddress.Any, 0);

        while (_running)
        {
            try
            {
                byte[] data = _udpClient.Receive(ref endPoint);
                string text = Encoding.UTF8.GetString(data);
                if (float.TryParse(text, NumberStyles.Float, CultureInfo.InvariantCulture, out float value))
                {
                    _latestScore = value;
                }
            }
            catch (SocketException)
            {
                if (!_running) break;
            }
            catch (ObjectDisposedException)
            {
                break;
            }
        }
    }

    private void OnDestroy()
    {
        _running = false;
        _udpClient?.Close();
        _listenThread?.Join(500);
    }
}
