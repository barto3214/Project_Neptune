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
        public string PacketType { get; set; } = "data"; 
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
            int score = 0;
            string criticalReason = null;

            // ═══ pH (waga: 40 punktów) ═══
            if (Ph < 4.0 || Ph > 10.0)
            {
                criticalReason = "pH out of safe range";
                score -= 100; // instant fail
            }
            else if (Ph >= 6.5 && Ph <= 8.5)
                score += 40; // idealny
            else if (Ph >= 6.0 && Ph <= 9.0)
                score += 20; // akceptowalny
            else
                score += 5;  // słaby

            // ═══ TDS (waga: 35 punktów) ═══
            if (Tds > 1000)
            {
                if (criticalReason == null) criticalReason = "High TDS";
                score -= 100;
            }
            else if (Tds < 50)
                score += 10; // destylowana - nie idealna do picia
            else if (Tds <= 150)
                score += 35; // doskonała
            else if (Tds <= 300)
                score += 30; // dobra
            else if (Tds <= 600)
                score += 15; // akceptowalna
            else
                score += 5;  // słaba

            // ═══ Conductivity (waga: 25 punktów) ═══
            if (Conductivity > 2000)
                score -= 20;
            else if (Conductivity <= 600)
                score += 25; // dobra
            else if (Conductivity <= 1200)
                score += 15; // akceptowalna
            else
                score += 5;  // wysoka

            // ═══ WYNIK KOŃCOWY ═══
            if (criticalReason != null)
                return $"CRITICAL - {criticalReason}";

            if (score >= 90)
                return "EXCELLENT";
            else if (score >= 70)
                return "GOOD";
            else if (score >= 50)
                return "ACCEPTABLE";
            else if (score >= 30)
                return "POOR";
            else
                return "UNACCEPTABLE";
        }
    }
}
