using System;
using System.IO;
using System.Media;

namespace CoreLicht {
sealed class VoiceAudio : IDisposable {
    readonly string directory;
    SoundPlayer player;
    public string PlayingId { get; private set; }

    public VoiceAudio(string dataDirectory) { directory=Path.Combine(dataDirectory,"voices"); }
    string FileFor(string id) {
        if(String.IsNullOrEmpty(id))return null;
        foreach(char ch in id)if(ch<'0'||ch>'9')return null;
        return Path.Combine(directory,id+".wav");
    }
    public bool Exists(string id) { var path=FileFor(id);return path!=null&&File.Exists(path); }
    public void Play(string id) {
        var path=FileFor(id);
        if(path==null||!File.Exists(path))throw new FileNotFoundException("Voice audio has not been exported.",path);
        Stop();
        player=new SoundPlayer(path);
        try { player.Load();player.Play();PlayingId=id; }
        catch { Stop();throw; }
    }
    public void Stop() {
        PlayingId=null;
        if(player!=null){player.Stop();player.Dispose();player=null;}
    }
    public void Dispose(){Stop();}
}
}
