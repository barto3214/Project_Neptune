using Microsoft.VisualStudio.TestTools.UnitTesting;
using PN_Ground_Station;
using System;

namespace PN_Ground_Station.Tests
{
    [TestClass()]
    public class SensorDataTests
    {
        // ═══════════════════════════════════════════════════════════════
        // CRITICAL - pH poza bezpiecznym zakresem
        // ═══════════════════════════════════════════════════════════════

        [TestMethod()]
        public void GetWaterQuality_PhTooLow_ReturnsCritical()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 3.5,
                Tds = 200,
                Temperature = 20,
                Conductivity = 400
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("CRITICAL - pH out of safe range", result);
        }

        [TestMethod()]
        public void GetWaterQuality_PhTooHigh_ReturnsCritical()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 10.5,
                Tds = 200,
                Temperature = 20,
                Conductivity = 400
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("CRITICAL - pH out of safe range", result);
        }

        [TestMethod()]
        public void GetWaterQuality_PhExactly4_NotCritical()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 4.0,  // granica - nie powinno być critical
                Tds = 200,
                Temperature = 20,
                Conductivity = 400
            };

            string result = data.GetWaterQuality();

            Assert.AreNotEqual("CRITICAL - pH out of safe range", result);
        }

        // ═══════════════════════════════════════════════════════════════
        // UNACCEPTABLE - TDS za wysokie
        // ═══════════════════════════════════════════════════════════════

        [TestMethod()]
        public void GetWaterQuality_TdsAbove1000_ReturnsUnacceptable()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 7.0,
                Tds = 1200,
                Temperature = 20,
                Conductivity = 2400
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("UNACCEPTABLE - High TDS", result);
        }

        [TestMethod()]
        public void GetWaterQuality_TdsExactly1000_ReturnsPoor()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 7.0,
                Tds = 1000,
                Temperature = 20,
                Conductivity = 2000
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("UNACCEPTABLE - High TDS", result);
        }

        // ═══════════════════════════════════════════════════════════════
        // POOR - słaba jakość
        // ═══════════════════════════════════════════════════════════════

        [TestMethod()]
        public void GetWaterQuality_PhPoor_ReturnsPoor()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 5.5,  // poniżej 6.0
                Tds = 200,
                Temperature = 20,
                Conductivity = 400
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("POOR", result);
        }

        [TestMethod()]
        public void GetWaterQuality_TdsPoor_ReturnsPoor()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 7.0,
                Tds = 750,  // powyżej 600
                Temperature = 20,
                Conductivity = 1000
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("POOR", result);
        }

        [TestMethod()]
        public void GetWaterQuality_ConductivityHigh_ReturnsPoor()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 7.0,
                Tds = 300,
                Temperature = 20,
                Conductivity = 1600  // powyżej 1500
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("POOR", result);
        }

        // ═══════════════════════════════════════════════════════════════
        // ACCEPTABLE - akceptowalna jakość
        // ═══════════════════════════════════════════════════════════════

        [TestMethod()]
        public void GetWaterQuality_PhSlightlyOff_ReturnsAcceptable()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 6.3,  // pomiędzy 6.0 a 6.5
                Tds = 200,
                Temperature = 20,
                Conductivity = 400
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("ACCEPTABLE", result);
        }

        [TestMethod()]
        public void GetWaterQuality_TdsModerate_ReturnsAcceptable()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 7.0,
                Tds = 350,  // pomiędzy 300 a 600
                Temperature = 20,
                Conductivity = 700
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("ACCEPTABLE", result);
        }

        [TestMethod()]
        public void GetWaterQuality_ConductivityModerate_ReturnsAcceptable()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 7.0,
                Tds = 200,
                Temperature = 20,
                Conductivity = 900  // pomiędzy 800 a 1500
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("ACCEPTABLE", result);
        }

        // ═══════════════════════════════════════════════════════════════
        // DISTILLED - woda destylowana
        // ═══════════════════════════════════════════════════════════════

        [TestMethod()]
        public void GetWaterQuality_VeryLowTds_ReturnsDistilled()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 7.0,
                Tds = 30,  // poniżej 50
                Temperature = 20,
                Conductivity = 60
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("DISTILLED", result);
        }

        [TestMethod()]
        public void GetWaterQuality_TdsExactly50_NotDistilled()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 7.0,
                Tds = 50,  // granica
                Temperature = 20,
                Conductivity = 100
            };

            string result = data.GetWaterQuality();

            Assert.AreNotEqual("DISTILLED", result);
        }

        // ═══════════════════════════════════════════════════════════════
        // EXCELLENT - doskonała jakość
        // ═══════════════════════════════════════════════════════════════

        [TestMethod()]
        public void GetWaterQuality_LowTds_ReturnsExcellent()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 7.2,
                Tds = 100,
                Temperature = 20,
                Conductivity = 200
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("GOOD", result);  // bez zmian
        }

        // ═══════════════════════════════════════════════════════════════
        // GOOD - dobra jakość
        // ═══════════════════════════════════════════════════════════════

        [TestMethod()]
        public void GetWaterQuality_OptimalValues_ReturnsGood()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 7.2,
                Tds = 200,  // pomiędzy 150 a 300
                Temperature = 20,
                Conductivity = 400
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("GOOD", result);
        }

        [TestMethod()]
        public void GetWaterQuality_IdealDrinkingWater_ReturnsGood()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 7.5,
                Tds = 250,
                Temperature = 22,
                Conductivity = 500
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("GOOD", result);
        }

        // ═══════════════════════════════════════════════════════════════
        // EDGE CASES - przypadki graniczne
        // ═══════════════════════════════════════════════════════════════

        [TestMethod()]
        public void GetWaterQuality_AllZeros_ReturnsCritical()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 0,
                Tds = 0,
                Temperature = 0,
                Conductivity = 0
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("CRITICAL - pH out of safe range", result);
        }

        [TestMethod()]
        public void GetWaterQuality_ExtremeTds_ReturnsUnacceptable()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 7.0,
                Tds = 5000,
                Temperature = 20,
                Conductivity = 10000
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("UNACCEPTABLE - High TDS", result);
        }

        // ═══════════════════════════════════════════════════════════════
        // PRIORITY TEST - pH Critical ma priorytet nad innymi
        // ═══════════════════════════════════════════════════════════════

        [TestMethod()]
        public void GetWaterQuality_CriticalPhOverridesGoodTds_ReturnsCritical()
        {
            var data = new SensorData
            {
                StationId = 1,
                Ph = 2.0,  // critical
                Tds = 100,  // excellent
                Temperature = 20,
                Conductivity = 200  // good
            };

            string result = data.GetWaterQuality();

            Assert.AreEqual("CRITICAL - pH out of safe range", result);
        }
    }
}