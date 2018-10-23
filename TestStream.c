 #include <stdio.h>
 #include <fcntl.h>
 #include <stdlib.h>
 #include <unistd.h>
 #include <stdbool.h>
 #include <inttypes.h>
 #include <string.h>

 #define F_LINUX_SPECIFIC_BASE	1024
 #define F_GET_RW_HINT		(F_LINUX_SPECIFIC_BASE + 11)
 #define F_SET_RW_HINT		(F_LINUX_SPECIFIC_BASE + 12)

#define CHUNKSIZE 512*1024
#define MAX_STREAM 8
int main(int argc, char *argv[])
{
	uint64_t hint,StreamIdx;
	int fd[MAX_STREAM * 2], ret, writen, itrycount, istream;
	char szFilePath[CHUNKSIZE],writeData[CHUNKSIZE];
	uint64_t iSize = 0;
	
	if (argc >= 3 )
	{
		istream = atoi(argv[1]);
		itrycount = atoi(argv[2]);
		printf("Test Stream on/off : %d, tricount : %d \n", istream, itrycount);
	}
	
	memset(writeData,'0',CHUNKSIZE);

	for( StreamIdx = 2 ; StreamIdx <= MAX_STREAM + 1; StreamIdx++ )
	{

		sprintf(szFilePath, "/media/unicorn/Gemini960G/TestStream_%d_%ld.txt",istream,StreamIdx);
	
		fd[StreamIdx] = open(szFilePath, O_RDWR|O_CREAT); 

		if (fd[StreamIdx] < 0) {printf("Open Error %s \n", szFilePath);}

		if (istream == 1)
		{		
			hint = StreamIdx;
			ret = fcntl(fd[StreamIdx], F_SET_RW_HINT, &hint);
			if (ret < 0) {	printf("Open Error : %s, hint : %ld\n", szFilePath, hint);}
		//	printf("File Open success : %s, with hint : %ld\n", szFilePath, hint);
		}
	}

	for ( int i = 0; i < itrycount; i++ )
	{			
		StreamIdx = i % MAX_STREAM + 2;

		writen = write(fd[StreamIdx], writeData, strlen(writeData));

		if (writen < 0) { printf("File write Fail : %s,hint : %ld\n", szFilePath, hint); }

		iSize = iSize + CHUNKSIZE;

		//printf("File Write success : %s, with hint : %ld\n", szFilePath, hint);
	}

	for( StreamIdx = 2 ; StreamIdx <= MAX_STREAM + 1; StreamIdx++ )
	{
		close(fd[StreamIdx]);
	}
	

	printf("File Write success Size: %ld \n", iSize);

	return 0;
}
