using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace PN_Ground_Station
{
    public class SensorData
    {
        public int StationId { get; set; }
        public double Ph { get; set; }
        public double Tds { get; set; }
        public double Temperature { get; set; }
        public double Conductivity { get; set; }
        public uint Timestamp { get; set; }
        public double BatteryVoltage { get; set; }
        public byte ErrorFlags { get; set; }
        public DateTime ReceivedAt { get; set; } = DateTime.Now;

       

        public override string ToString()
        {
            return $"[{ReceivedAt:HH:mm:ss}] pH={Ph:F2}, TDS={Tds:F1}ppm, Temp={Temperature:F1}°C, Cond={Conductivity:F0}µS/cm";
        }


        /// Check if data is in valid ranges
        public bool IsValid()
        {
            return Ph >= 0 && Ph <= 14 &&
                   Temperature >= -10 && Temperature <= 50 &&
                   Tds >= 0 && Tds <= 5000 &&
                   Conductivity >= 0 && Conductivity <= 10000;
        }


        /// Get pH status description
        public string GetPhStatus()
        {
            if (Ph < 6.5) return "Acidic";
            if (Ph > 8.5) return "Alkaline";
            return "Neutral";
        }


        /// Get water quality based on TDS
        public string GetWaterQuality()
        {
            if (Tds < 50) return "Distilled";
            if (Tds < 150) return "Excellent";
            if (Tds < 300) return "Good";
            if (Tds < 500) return "Acceptable";
            if (Tds < 1000) return "Poor";
            return "Unacceptable";
        }
    }
}
