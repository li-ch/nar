#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/flow-monitor-helper.h"
#include "ns3/internet-module.h"
#include "ns3/cc-algo.h"
#include "ns3/ipv4-flow-classifier.h"
#include "ns3/network-module.h"
#include "ns3/point-to-point-module.h"
#include "ns3/traffic-control-module.h"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <map>
#include <sstream>
#include <string>
#include <vector>

using namespace ns3;

namespace
{

struct ScenarioConfig
{
    std::string name;
    uint32_t numFlows;
    double durationSec;
    bool dynamicBottleneck;
};

struct FlowSummary
{
    uint32_t flowId;
    double throughputMbps;
    double avgDelayMs;
    uint64_t rxBytes;
};

void
WriteSummaryCsv(const std::string& path, const std::vector<FlowSummary>& rows)
{
    std::ofstream out(path, std::ios::out | std::ios::trunc);
    out << "flow_id,throughput_mbps,avg_delay_ms,rx_bytes\n";
    for (const auto& r : rows)
    {
        out << r.flowId << "," << std::fixed << std::setprecision(6) << r.throughputMbps << ","
            << r.avgDelayMs << "," << r.rxBytes << "\n";
    }
}

std::vector<FlowSummary>
CollectSummaries(Ptr<FlowMonitor> monitor,
                 Ptr<Ipv4FlowClassifier> classifier,
                 const std::map<uint16_t, uint32_t>& portToFlow,
                 double durationSec)
{
    std::vector<FlowSummary> out;
    const auto stats = monitor->GetFlowStats();
    for (const auto& [flowId, st] : stats)
    {
        const auto fiveTuple = classifier->FindFlow(flowId);
        auto it = portToFlow.find(fiveTuple.destinationPort);
        if (it == portToFlow.end())
        {
            continue;
        }
        FlowSummary row;
        row.flowId = it->second;
        row.rxBytes = st.rxBytes;
        row.throughputMbps = durationSec > 0 ? (8.0 * st.rxBytes) / (durationSec * 1e6) : 0.0;
        row.avgDelayMs = st.rxPackets > 0 ? (1000.0 * st.delaySum.GetSeconds() / st.rxPackets) : 0.0;
        out.push_back(row);
    }
    return out;
}

void
RunScenario(const ScenarioConfig& cfg, const std::string& algorithm, const std::string& outputDir)
{
    NodeContainer senders;
    senders.Create(cfg.numFlows);
    NodeContainer receivers;
    receivers.Create(cfg.numFlows);
    NodeContainer routers;
    routers.Create(2);

    InternetStackHelper internet;
    internet.Install(senders);
    internet.Install(receivers);
    internet.Install(routers);

    PointToPointHelper access;
    access.SetDeviceAttribute("DataRate", StringValue("100Mbps"));
    access.SetChannelAttribute("Delay", StringValue("1ms"));

    PointToPointHelper bottleneck;
    bottleneck.SetDeviceAttribute("DataRate", StringValue("10Mbps"));
    bottleneck.SetChannelAttribute("Delay", StringValue("10ms"));

    TrafficControlHelper tch;
    tch.SetRootQueueDisc("ns3::FqCoDelQueueDisc");

    NetDeviceContainer bottleneckDevices = bottleneck.Install(routers.Get(0), routers.Get(1));
    tch.Install(bottleneckDevices);

    std::vector<NetDeviceContainer> senderDevices;
    std::vector<NetDeviceContainer> receiverDevices;
    senderDevices.reserve(cfg.numFlows);
    receiverDevices.reserve(cfg.numFlows);
    for (uint32_t i = 0; i < cfg.numFlows; ++i)
    {
        senderDevices.push_back(access.Install(senders.Get(i), routers.Get(0)));
        receiverDevices.push_back(access.Install(routers.Get(1), receivers.Get(i)));
    }

    Ipv4AddressHelper ipv4;
    std::vector<Ipv4InterfaceContainer> senderIfs(cfg.numFlows);
    std::vector<Ipv4InterfaceContainer> receiverIfs(cfg.numFlows);

    ipv4.SetBase("10.0.0.0", "255.255.255.0");
    Ipv4InterfaceContainer bottleneckIf = ipv4.Assign(bottleneckDevices);

    for (uint32_t i = 0; i < cfg.numFlows; ++i)
    {
        std::ostringstream a;
        a << "10.1." << i << ".0";
        ipv4.SetBase(a.str().c_str(), "255.255.255.0");
        senderIfs[i] = ipv4.Assign(senderDevices[i]);

        std::ostringstream b;
        b << "10.2." << i << ".0";
        ipv4.SetBase(b.str().c_str(), "255.255.255.0");
        receiverIfs[i] = ipv4.Assign(receiverDevices[i]);
    }

    Ipv4GlobalRoutingHelper::PopulateRoutingTables();

    TypeId tcpTid;
    if (algorithm == "TcpAutoCC")
    {
        tcpTid = TcpAutoCC::GetTypeId();
    }
    else if (!TypeId::LookupByNameFailSafe("ns3::" + algorithm, &tcpTid))
    {
        NS_FATAL_ERROR("Unknown TCP algorithm: " << algorithm);
    }
    Config::SetDefault("ns3::TcpL4Protocol::SocketType", TypeIdValue(tcpTid));

    std::map<uint16_t, uint32_t> portToFlow;
    std::vector<Ptr<PacketSink>> sinks;
    sinks.reserve(cfg.numFlows);

    ApplicationContainer sinkApps;
    ApplicationContainer sourceApps;
    for (uint32_t i = 0; i < cfg.numFlows; ++i)
    {
        uint16_t port = static_cast<uint16_t>(5000 + i);
        portToFlow.emplace(port, i);

        Address sinkLocalAddress(InetSocketAddress(Ipv4Address::GetAny(), port));
        PacketSinkHelper sinkHelper("ns3::TcpSocketFactory", sinkLocalAddress);
        auto sinkApp = sinkHelper.Install(receivers.Get(i));
        sinkApps.Add(sinkApp);

        BulkSendHelper source("ns3::TcpSocketFactory",
                              InetSocketAddress(receiverIfs[i].GetAddress(1), port));
        source.SetAttribute("MaxBytes", UintegerValue(0));
        auto sourceApp = source.Install(senders.Get(i));
        sourceApps.Add(sourceApp);

        double start = (cfg.name == "scenario_b") ? (2.0 + 4.0 * i) : 2.0;
        sourceApp.Start(Seconds(start));
        sourceApp.Stop(Seconds(cfg.durationSec));
    }

    sinkApps.Start(Seconds(0.5));
    sinkApps.Stop(Seconds(cfg.durationSec + 1.0));

    for (uint32_t i = 0; i < sinkApps.GetN(); ++i)
    {
        auto sink = DynamicCast<PacketSink>(sinkApps.Get(i));
        sinks.push_back(sink);
    }

    const std::string tsPath = outputDir + "/" + cfg.name + "_timeseries.csv";
    std::ofstream ts(tsPath, std::ios::out | std::ios::trunc);
    ts << "timestamp_s,flow_id,throughput_mbps,cwnd_bytes,rtt_ms\n";

    std::vector<uint64_t> prevBytes(cfg.numFlows, 0);
    std::function<void()> sample = [&]() {
        const double now = Simulator::Now().GetSeconds();
        for (uint32_t i = 0; i < cfg.numFlows; ++i)
        {
            uint64_t cur = sinks[i]->GetTotalRx();
            double mbps = (8.0 * static_cast<double>(cur - prevBytes[i])) / (0.1 * 1e6);
            prevBytes[i] = cur;
            ts << std::fixed << std::setprecision(3) << now << "," << i << "," << std::setprecision(6)
               << mbps << ",-1,-1\n";
        }
        if (now + 0.1 <= cfg.durationSec)
        {
            Simulator::Schedule(Seconds(0.1), sample);
        }
    };
    Simulator::Schedule(Seconds(0.1), sample);

    if (cfg.dynamicBottleneck)
    {
        Simulator::Schedule(Seconds(30.0), [=]() {
            bottleneckDevices.Get(0)->SetAttribute("DataRate", DataRateValue(DataRate("5Mbps")));
            bottleneckDevices.Get(1)->SetAttribute("DataRate", DataRateValue(DataRate("5Mbps")));
        });
        Simulator::Schedule(Seconds(45.0), [=]() {
            bottleneckDevices.Get(0)->SetAttribute("DataRate", DataRateValue(DataRate("10Mbps")));
            bottleneckDevices.Get(1)->SetAttribute("DataRate", DataRateValue(DataRate("10Mbps")));
        });
    }

    FlowMonitorHelper flowmon;
    Ptr<FlowMonitor> monitor = flowmon.InstallAll();

    Simulator::Stop(Seconds(cfg.durationSec + 1.0));
    Simulator::Run();
    ts.close();

    monitor->CheckForLostPackets();
    auto classifier = DynamicCast<Ipv4FlowClassifier>(flowmon.GetClassifier());
    auto rows = CollectSummaries(monitor, classifier, portToFlow, cfg.durationSec);
    WriteSummaryCsv(outputDir + "/" + cfg.name + "_summary.csv", rows);

    Simulator::Destroy();
}

} // namespace

int
main(int argc, char* argv[])
{
    std::string algorithm = "TcpAutoCC";
    std::string outputDir = "artifacts/cc/traces";
    CommandLine cmd(__FILE__);
    cmd.AddValue("algorithm", "TCP algorithm (e.g. TcpAutoCC, TcpCubic)", algorithm);
    cmd.AddValue("output_dir", "Directory for trace csv outputs", outputDir);
    cmd.Parse(argc, argv);

    std::filesystem::create_directories(outputDir);

    std::vector<ScenarioConfig> scenarios = {
        {"scenario_a", 1, 60.0, false},
        {"scenario_b", 5, 60.0, false},
        {"scenario_c", 1, 60.0, true},
    };

    for (const auto& s : scenarios)
    {
        RunScenario(s, algorithm, outputDir);
    }

    return 0;
}
