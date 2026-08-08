#include <simgrid/s4u.hpp>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace sg4 = simgrid::s4u;
static constexpr double INTERVAL_SECONDS = 0.1;

struct Flow {
  unsigned long long id = 0;
  int src = -1;
  int dst = -1;
  int start_interval = 0;
  double gbit = 0.0;
};

struct Result {
  unsigned long long id = 0;
  int src = -1;
  int dst = -1;
  double start = 0.0;
  double finish = 0.0;
};

static std::vector<Result> results;

static std::vector<std::string> split_csv(const std::string& line)
{
  std::vector<std::string> out;
  std::stringstream ss(line);
  std::string field;
  while (std::getline(ss, field, ',')) out.push_back(field);
  return out;
}

static std::vector<Flow> load_flows(const std::string& path)
{
  std::ifstream in(path);
  if (!in) throw std::runtime_error("cannot open traffic CSV: " + path);
  std::string line;
  if (!std::getline(in, line)) throw std::runtime_error("empty traffic CSV");
  if (!line.empty() && line.back() == '\r') line.pop_back();
  if (line != "interval,flow_id,source_terminal,destination_terminal,offered_gbit")
    throw std::runtime_error("unexpected traffic CSV header: " + line);

  std::vector<Flow> flows;
  while (std::getline(in, line)) {
    if (!line.empty() && line.back() == '\r') line.pop_back();
    if (line.empty()) continue;
    const auto f = split_csv(line);
    if (f.size() != 5) throw std::runtime_error("malformed traffic row: " + line);
    Flow flow;
    flow.start_interval = std::stoi(f[0]);
    flow.id = std::stoull(f[1]);
    flow.src = std::stoi(f[2]);
    flow.dst = std::stoi(f[3]);
    flow.gbit = std::stod(f[4]);
    flows.push_back(flow);
  }
  return flows;
}

static void receiver(const std::string& mailbox_name)
{
  auto* mailbox = sg4::Mailbox::by_name(mailbox_name);
  auto* payload = mailbox->get<unsigned long long>();
  delete payload;
}

static void sender(const Flow flow)
{
  const double requested_start = static_cast<double>(flow.start_interval) * INTERVAL_SECONDS;
  if (requested_start > sg4::Engine::get_clock()) sg4::this_actor::sleep_until(requested_start);

  const std::string mailbox_name = "flow-" + std::to_string(flow.id);
  auto* mailbox = sg4::Mailbox::by_name(mailbox_name);
  const std::uint64_t bytes = static_cast<std::uint64_t>(std::llround(flow.gbit * 1.0e9 / 8.0));
  const double start = sg4::Engine::get_clock();
  mailbox->put(new unsigned long long(flow.id), bytes);
  const double finish = sg4::Engine::get_clock();
  results.push_back(Result{flow.id, flow.src, flow.dst, start, finish});
}

int main(int argc, char** argv)
{
  sg4::Engine engine(&argc, argv);
  if (argc != 4) {
    std::fprintf(stderr, "usage: %s platform.xml traffic.csv fct.csv\n", argv[0]);
    return 2;
  }

  engine.load_platform(argv[1]);
  const auto flows = load_flows(argv[2]);
  results.reserve(flows.size());

  for (const auto& flow : flows) {
    auto* dst = engine.host_by_name("T" + std::to_string(flow.dst));
    sg4::Actor::create("recv-" + std::to_string(flow.id), dst, receiver,
                       "flow-" + std::to_string(flow.id));
  }
  for (const auto& flow : flows) {
    auto* src = engine.host_by_name("T" + std::to_string(flow.src));
    sg4::Actor::create("send-" + std::to_string(flow.id), src, sender, flow);
  }

  engine.run();
  std::sort(results.begin(), results.end(), [](const Result& a, const Result& b) { return a.id < b.id; });

  std::ofstream out(argv[3]);
  if (!out) throw std::runtime_error("cannot open FCT output");
  out << "flow_id,source_terminal,destination_terminal,start_sec,finish_sec,fct_sec\n";
  for (const auto& r : results)
    out << r.id << ',' << r.src << ',' << r.dst << ',' << r.start << ',' << r.finish << ','
        << (r.finish - r.start) << '\n';
  return 0;
}
