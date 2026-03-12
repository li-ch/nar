#include "cc-algo.h"

#include "ns3/log.h"

#include <algorithm>

namespace ns3 {

NS_LOG_COMPONENT_DEFINE("TcpAutoCC");
NS_OBJECT_ENSURE_REGISTERED(TcpAutoCC);

TypeId
TcpAutoCC::GetTypeId()
{
    static TypeId tid = TypeId("ns3::TcpAutoCC")
                            .SetParent<TcpCongestionOps>()
                            .SetGroupName("Internet")
                            .AddConstructor<TcpAutoCC>();
    return tid;
}

TcpAutoCC::TcpAutoCC()
    : TcpCongestionOps()
{
}

TcpAutoCC::TcpAutoCC(const TcpAutoCC& sock)
    : TcpCongestionOps(sock)
{
}

std::string
TcpAutoCC::GetName() const
{
    return "TcpAutoCC";
}

uint32_t
TcpAutoCC::GetSsThresh(Ptr<const TcpSocketState> tcb, uint32_t bytesInFlight)
{
    return std::max(2 * tcb->m_segmentSize, bytesInFlight / 2);
}

void
TcpAutoCC::IncreaseWindow(Ptr<TcpSocketState> tcb, uint32_t segmentsAcked)
{
    if (segmentsAcked == 0)
    {
        return;
    }

    if (tcb->m_cWnd < tcb->m_ssThresh)
    {
        // Slow start: +1 MSS per ACK.
        tcb->m_cWnd += tcb->m_segmentSize * segmentsAcked;
    }
    else
    {
        // Congestion avoidance: roughly +1 MSS per RTT.
        const double adder =
            static_cast<double>(tcb->m_segmentSize * tcb->m_segmentSize) / tcb->m_cWnd.Get();
        const uint32_t delta = static_cast<uint32_t>(std::max(1.0, adder));
        tcb->m_cWnd += delta * segmentsAcked;
    }
}

Ptr<TcpCongestionOps>
TcpAutoCC::Fork()
{
    return CreateObject<TcpAutoCC>(*this);
}

} // namespace ns3
