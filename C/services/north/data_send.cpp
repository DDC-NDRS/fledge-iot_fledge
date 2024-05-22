/*
 * Fledge North Service Data Loading.
 *
 * Copyright (c) 2020, 2024 Dianomic Systems
 *
 * Released under the Apache 2.0 Licence
 *
 * Author: Mark Riddoch, Massimiliano Pinto
 */
#include <data_sender.h>
#include <data_load.h>
#include <north_service.h>
#include <reading.h>

using namespace std;

/**
 * Start the sending thread within the DataSender class
 *
 * @param data	The instance of the class DataSender
 */
static void startSenderThread(void *data)
{
	DataSender *sender = (DataSender *)data;
	sender->sendThread();
}

/**
 * Thread to update statistics table in DB
 */
static void statsThread(DataSender *sender)
{
	while (sender->isRunning())
	{
		sender->flushStatistics();
	}
}

/**
 * Constructor for the data sending class
 */
DataSender::DataSender(NorthPlugin *plugin, DataLoad *loader, NorthService *service) :
	m_plugin(plugin), m_loader(loader), m_service(service), m_shutdown(false), m_paused(false), m_perfMonitor(NULL)
{
	m_statsUpdateFails = 0;

	m_logger = Logger::getLogger();

	// Create statistics rows if not existant
	if (createStats("Readings Sent", 0))
	{
		m_statsDbEntriesCache.insert("Readings Sent");
	}
	if (createStats(m_loader->getName(), 0))
	{
		m_statsDbEntriesCache.insert(m_loader->getName());
	}

	/*
	 * Start the thread. Everything must be initialsied
	 * before the thread is started
	 */
	m_thread = new thread(startSenderThread, this);

	m_statsThread = new thread(statsThread, this);
}

/**
 * Destructor for the data sender class
 */
DataSender::~DataSender()
{
	m_logger->info("DataSender shutdown in progress");
	m_shutdown = true;
	m_thread->join();
	delete m_thread;

	m_statsCv.notify_one();
	m_logger->debug("DataSender stats thread notified");
	m_statsThread->join();
	m_logger->debug("DataSender stats thread joined");
	delete m_statsThread;

	m_logger->info("DataSender shutdown complete");
}

/**
 * The sending thread entry point
 */
void DataSender::sendThread()
{
	ReadingSet *readings = nullptr;

	while (!m_shutdown)
	{
		if (readings == NULL) {

			readings = m_loader->fetchReadings(true);
		}
		if (!readings)
		{
			m_logger->warn(
				"Sending thread closing down after failing to fetch readings");
			return;
		}
		bool removeReadings = false;
		if (readings->getCount() > 0)
		{
			unsigned long lastSent = send(readings);
			if (lastSent)
			{
				m_loader->updateLastSentId(lastSent);

				// Check all readings sent
				vector<Reading *> *vec = readings->getAllReadingsPtr();

				// Set readings removal
				removeReadings = vec->size() == 0;
			}
		} else {
			// All readings filtered out
			Logger::getLogger()->debug("All readings filtered out");

			// Get last read item from the readings database
			unsigned long lastRead = m_loader->getLastFetched();

			// Update LastSentId in streams table
			m_loader->updateLastSentId(lastRead);

			// Set readings removal
			removeReadings = true;
		}

		// Remove readings object if needed
		if (removeReadings)
		{
			delete readings;
			readings = NULL;
		}
	}
	if (readings)
	{
		// Rremove any readings we had failed to send before shutting down
		delete readings;
	}
	m_logger->info("Sending thread shutdown");
}

/**
 * Send a block of readings
 *
 * @param readings	The readings to send
 * @return long		The ID of the last reading sent
 */
unsigned long DataSender::send(ReadingSet *readings)
{
	blockPause();
	uint32_t to_send = readings->getCount();
	uint32_t sent = m_plugin->send(readings->getAllReadings());
	releasePause();

    // last few readings in the reading set may have 0 reading ID, 
    // if they have been generated by filters on north service itself
    const std::vector<Reading *>& readingsVec = readings->getAllReadings();
    unsigned long lastSent = 0;
    for(auto rdngPtrItr = readingsVec.crbegin(); rdngPtrItr != readingsVec.crend(); rdngPtrItr++)
    {
        if((*rdngPtrItr)->hasId()) // only consider readings with valid reading IDs
        {
            lastSent = (*rdngPtrItr)->getId();
            break;
        }
    }
    
	// unsigned long lastSent = readings->getReadingId(sent);
	if (m_perfMonitor)
	{
		m_perfMonitor->collect("Readings sent", sent);
		m_perfMonitor->collect("Percentage readings sent", (100 * sent) / to_send);
	}

	Logger::getLogger()->debug("DataSender::send(): to_send=%d, sent=%d, lastSent=%lu", to_send, sent, lastSent);

	if (sent > 0)
	{
		// lastSent = readings->getLastId();

		// Update asset tracker table/cache, if required
		vector<Reading *> *vec = readings->getAllReadingsPtr();

		for (vector<Reading *>::iterator it = vec->begin(); it != vec->end(); )
		{
			Reading *reading = *it;

			if (!reading->hasId() || reading->getId() <= lastSent)
			{
				AssetTrackingTuple tuple(m_service->getName(), m_service->getPluginName(), reading->getAssetName(), "Egress");
				if (!AssetTracker::getAssetTracker()->checkAssetTrackingCache(tuple))
				{
					AssetTracker::getAssetTracker()->addAssetTrackingTuple(tuple);
					m_logger->info("sendDataThread:  Adding new asset tracking tuple - egress: %s", tuple.assetToString().c_str());
				}

				// Remove current reading
				delete reading;
				reading = NULL;

				// Remove item and set iterator to next element
				it = vec->erase(it);
			}
			else
			{
				break;
			}
		}
		updateStatistics(sent);
		return lastSent;
	}
	return 0;
}

/**
 * Cause the data sender process to pause sending data until a corresponding release call is made.
 *
 * This call does not block until release is called, but does block until the current
 * send completes.
 *
 * Called by external classes that want to prevent interaction
 * with the north plugin.
 */
void DataSender::pause()
{
	unique_lock<mutex> lck(m_pauseMutex);
	m_pauseCV.wait(lck, [this]{ return m_sending == false; });

	m_paused = true;
}

/**
 * Release the paused data sender thread
 *
 * Called by external classes that want to release interaction
 * with thew north plugin.
 */
void DataSender::release()
{
	{
		std::lock_guard<std::mutex> lck(m_pauseMutex);
		m_paused = false;
	}

	m_pauseCV.notify_all();
}

/**
 * Check if we have paused the sending of data
 *
 * Called before we interact with the north plugin by the
 * DataSender class
 */
void DataSender::blockPause()
{
	unique_lock<mutex> lck(m_pauseMutex);
	m_pauseCV.wait(lck, [this]{ return m_paused == false; });

	m_sending = true;
}

/*
 * Release the block on pausing the sender
 *
 * Called after we interact with the north plugin by the
 * DataSender class
 */
void DataSender::releasePause()
{
	{
		std::lock_guard<std::mutex> lck(m_pauseMutex);
		m_sending = false;
	}
	m_pauseCV.notify_all();
}

/**
 * Update the sent statistics
 *
 * @param increment     Increment of the number of readings sent
 */
void DataSender::updateStatistics(uint32_t increment)
{
	lock_guard<mutex> guard(m_statsMtx);

	// Add statistics counter to the map
	m_statsPendingEntries[m_loader->getName()] += increment;
	m_statsPendingEntries["Readings Sent"] += increment;
}

/**
 * Flush statistics to storage service
 */
void DataSender::flushStatistics()
{
	// Wait for FLUSH_STATS_INTERVAL seconds or receive notification
	// when shutdown is called
	unique_lock<mutex> flush(m_flushStatsMtx);
	m_statsCv.wait_for(flush, std::chrono::seconds(FLUSH_STATS_INTERVAL));
	flush.unlock();

	std::map<std::string, int> statsData;

	// Acquire m_statsMtx lock for m_statsMtx
	unique_lock<mutex> lck(m_statsMtx);

	// copy statistics map
	statsData = m_statsPendingEntries;

	// Reset statistics
	m_statsPendingEntries.clear();

	// Release lock
	lck.unlock();

	if (statsData.empty())
	{
		return;
	}

	vector<pair<ExpressionValues *, Where *>> statsUpdates;
	const Condition conditionStat(Equals);

	// Send statistics to storage service
	map<string, int>::iterator it;
	for (it = statsData.begin(); it != statsData.end(); it++)
	{
		// Prepare "WHERE key = name
		Where *nStat = new Where("key", conditionStat, it->first);
		// Prepare value = value + inc
		ExpressionValues *updateValue = new ExpressionValues;
		updateValue->push_back(Expression("value", "+", (int) it->second));

		statsUpdates.emplace_back(updateValue, nStat);

		// Check whether to create stats entry into the storage
		if (m_statsDbEntriesCache.find(it->first) == m_statsDbEntriesCache.end())
		{
			if (createStats(it->first, it->second))
			{
				m_statsDbEntriesCache.insert(it->first);
			}
		}

		Logger::getLogger()->error("Flushing '%s': %d",
				it->first.c_str(),
				it->second);
	}

	// Bulk update
	if (m_loader->getStorage())
	{
		// Do the update
		int rv = m_loader->getStorage()->updateTable("statistics", statsUpdates);

		// Check for errors
		if (rv != statsData.size())
		{
			if (++m_statsUpdateFails > STATS_UPDATE_FAIL_THRESHOLD)
			{
				Logger::getLogger()->warn("Update of statistics failure has persisted, attempting recovery");

				m_statsDbEntriesCache.clear();
				// Create statistics rows if not existant
				if (createStats("Readings Sent", 0))
				{
					m_statsDbEntriesCache.insert("Readings Sent");
				}
				if (createStats(m_loader->getName(), 0))
				{
					m_statsDbEntriesCache.insert(m_loader->getName());
				}

				m_statsUpdateFails = 0;
			}
			else if (m_statsUpdateFails == 1)
			{
				Logger::getLogger()->warn("Update of statistics failed");
			}
			else
			{
				Logger::getLogger()->warn("Update of statistics still failing");
			}
		}
	}
}

/**
 * Create a row into statistic table for each statistic
 *
 * @param key		The statistics key to create
 * @param value		The statistics value
 * @return		True for created data, False for no operation or error
 */
bool DataSender::createStats(const std::string &key,
		int value)
{
	if (!m_loader->getStorage())
	{
		return false;
	}

	// SELECT * FROM fledge.statiatics WHERE key = statistics_key
	const Condition conditionKey(Equals);
	Where *wKey = new Where("key", conditionKey, key);
	Query qKey(wKey);

	ResultSet* result = 0;

	// Query via storage client
	result = m_loader->getStorage()->queryTable("statistics", qKey);

	bool doInsert = !result->rowCount();
	delete result;

	if (!doInsert)
 	{
		// Row already exists
		return true;
	}

	string description;
	if (key == m_loader->getName())
	{
		description = key + " Readings Sent";
	}
	else
	{
		description = key + " Noth";
	}
	InsertValues values;
	values.push_back(InsertValue("key",         key));
	values.push_back(InsertValue("description", description));
	values.push_back(InsertValue("value",       value));
	string table = "statistics";

	if (m_loader->getStorage()->insertTable(table, values) != 1)
	{
		Logger::getLogger()->error("Failed to insert a new "\
				"row into the 'statistics' table, key '%s'",
				key.c_str());
		return false;
	}
	else
	{
		Logger::getLogger()->info("New row added into 'statistics' table, key '%s'",
			key.c_str());
		return true;
	}

	return false;
}
