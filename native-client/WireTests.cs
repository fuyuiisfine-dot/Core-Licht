using System;
using System.IO;
using System.Linq;
using CoreLicht;
class WireTests {
    public static int Main(string[] args) {
        try {
            var proto=new Proto(args[0]);var fixture=Data.Read(args[1]);int count=0;
            foreach(var entry in Data.Items(fixture["cases"])) {
                var c=Data.Map(entry);string direction=Data.Text(c["direction"]),id=Data.Text(c["id"]);
                byte[] expected=Convert.FromBase64String(Data.Text(c["bytes"]));
                byte[] actual=proto.Encode(direction,id,Data.Map(c["values"]));
                if(!expected.SequenceEqual(actual))throw new Exception("Python/C# encoding mismatch: "+direction+" "+id);
                var decoded=proto.Decode(direction,id,expected);
                if(!expected.SequenceEqual(proto.Encode(direction,id,decoded)))throw new Exception("Round trip mismatch: "+direction+" "+id);
                count++;
            }
            bool rejected=false;try{proto.Decode("c2s","1_1",new byte[]{128});}catch(EndOfStreamException){rejected=true;}
            if(!rejected)throw new Exception("Malformed message was accepted");
            Console.WriteLine("Verified Python/C# protobuf cases: "+count);return 0;
        }catch(Exception ex){Console.Error.WriteLine(ex);return 1;}
    }
}
