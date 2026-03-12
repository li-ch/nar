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
        return;
    }

    // Congestion avoidance with delay-gradient scaling.
    // Scale back growth linearly as queueing delay (lastRtt - minRtt) rises.
    double scale = 1.0;
    Time minRtt = tcb->m_minRtt;
    Time lastRtt = tcb->m_lastRtt;
    if (!minRtt.IsZero() && !lastRtt.IsZero() && lastRtt > minRtt)
    {
        double qd_ms = (lastRtt - minRtt).GetMilliSeconds();
        const double kTarget = 5.0;  // tolerate up to 5 ms of queuing
        const double kCeil   = 25.0; // stop growing at 25 ms of queuing
        if (qd_ms >= kCeil)
        {
            scale = 0.0;
        }
        else if (qd_ms > kTarget)
        {
            scale = 1.0 - (qd_ms - kTarget) / (kCeil - kTarget);
        }
    }

    if (scale > 0.0)
    {
        const double adder =
            static_cast<double>(tcb->m_segmentSize * tcb->m_segmentSize) / tcb->m_cWnd.Get();
        const uint32_t delta = static_cast<uint32_t>(std::max(1.0, adder));
        tcb->m_cWnd += static_cast<uint32_t>(delta * segmentsAcked * scale + 0.5);
    }
}

Ptr<TcpCongestionOps>
TcpAutoCC::Fork()
{
    return CreateObject<TcpAutoCC>(*this);
}

} // namespace ns3
